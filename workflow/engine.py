"""Simulation ledger and integer-lot robust portfolio optimizer. Run from repo root."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
from pathlib import Path

import numpy as np
from contextlib import contextmanager
from scipy.optimize import Bounds, LinearConstraint, milp

R = Path("result")
META = R / "simulation.json"
POS = R / "current-portfolio.csv"
LOG = R / "trade-log.csv"
JOURNAL = R / ".pending-write.json"
PH = "asset,quantity,average_cost,latest_price,value,weight".split(",")
TH = "quarter,trade_id,asset,side,quantity,price,amount,realized_pnl,fee".split(",")


@contextmanager
def locked():
    with (R / ".simulation.lock").open("a+b") as f:
        if os.name == "nt":
            import msvcrt
            if f.tell() == 0:
                f.write(b"0")
                f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        yield


def require(test, message):
    if not test:
        raise ValueError(message)


def number(x):
    x = float(x)
    require(math.isfinite(x), "Non-finite number")
    return x


def table(header, rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return out.getvalue()


def read(path):
    return path.read_text(encoding="utf-8-sig") if path.exists() else ""


def archive(source, digest):
    path = Path("data/evidence") / (digest + Path(source).suffix.lower())
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = Path(source).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==digest,"Source changed during ingestion")
    if path.exists():
        require(path.read_bytes()==raw,"Archived evidence differs")
    else:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(f.name,path)


def atomic(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w",
                                     encoding="utf-8", newline="") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, path)


def recover():
    if JOURNAL.exists():
        for path, content in json.loads(read(JOURNAL)).items():
            atomic(path, content)
        JOURNAL.unlink()


def rules():
    raw = read(Path("workflow/constraints.md"))
    def get(label):
        match = re.search(re.escape(label) + r"(?:\s*\|\s*|:\s*)(?:USD )?([\d,.]+)", raw)
        require(match, "Missing constraint " + label)
        return number(match[1].replace(",", "").rstrip("."))
    require("Short Selling | Not Allowed" in raw and "Assume no leverage" in raw,
            "Mandate changed. Review model.")
    return dict(capital=get("Initial Capital"), quarters=int(get("Number of Quarters")),
                minimum=get("Minimum Investment Ratio at Quarter Start"),
                cap=get("Maximum Exposure per Financial Product"),
                loss=get("Maximum Loss per Trade"), dev=get("Maximum Benchmark Weight Deviation"),
                version=re.search(r"Version: (.+)", raw)[1], hash=hashlib.sha256(raw.encode()).hexdigest())


def optimize(values, units, lot, cash, weights, scenarios, adverse, costs, r, start):
    # Integer target lots, absolute turnover dollars, worst scenario profit.
    n = len(units)
    nav = cash + sum(values)
    step = np.array(lot)
    lo = np.maximum(0, weights - r["dev"]) * nav
    hi = np.minimum((weights + r["dev"]) * nav, r["cap"])
    hi = np.minimum(hi, r["loss"] / adverse)
    rows, lbs, ubs = [], [], []
    def row(a, b, c, lower, upper):
        rows.append(np.r_[a, b, c])
        lbs.append(lower)
        ubs.append(upper)
    zero = np.zeros(n)
    row(step, zero, 0, nav * r["minimum"] if start else 0, nav)
    for i, eye in enumerate(np.eye(n)):
        row(step * eye, -eye, 0, -np.inf, values[i])
        row(-step * eye, -eye, 0, -np.inf, -values[i])
        # Realized loss on the proposed sale, using average cost.
        if costs[i] > 0:
            row(eye * costs[i], zero, 0, units[i] * costs[i] - r["loss"], np.inf)
    for s in scenarios:
        row(step * s, zero, -1, 0, np.inf)
    bounds = Bounds(np.r_[np.ceil(lo / step - 1e-10), zero, -np.inf],
                    np.r_[np.floor(hi / step + 1e-10), np.full(n, np.inf), np.inf])
    def solve(obj):
        sol = milp(obj, integrality=np.r_[np.ones(n), zero, 0], bounds=bounds,
                   constraints=LinearConstraint(rows, lbs, ubs))
        require(sol.success, "No verified feasible optimum: " + sol.message)
        return sol.x
    best = solve(np.r_[zero, zero, -1])
    row(zero, zero, 1, best[-1] - max(1e-7, abs(best[-1])*1e-9), np.inf)
    target = np.rint(solve(np.r_[zero, np.ones(n), 0])[:n])
    v = target * step
    require(np.all(v >= lo-1e-6) and np.all(v <= hi+1e-6) and sum(v) <= nav+1e-6
            and (not start or sum(v) >= nav*r["minimum"]-1e-6)
            and np.all((units-target)*costs <= r["loss"]+1e-6), "Post-rounding constraint failure")
    return target


def run(action, d):
    recover()
    r = rules()
    m = json.loads(read(META) or '{"q":1,"stage":"new","seen":[]}')
    if action == "status":
        return m
    q = m["q"]
    pending = m.get("pending")
    changes = {}
    def save(path, content):
        changes[str(path)] = content
    def append(path, content):
        save(path, read(path) + content)
    if action == "build" and m["stage"] == "new":
        require(all(read(path).strip() in ("",table(header,[]).strip()) for path,header in ((LOG,TH),(POS,PH))),
                "Existing ledgers require reconciliation")
        path = Path("data/benchmark.csv")
        raw = table(["asset","price","weight","lot"], d["benchmark"])
        if read(path).strip():
            require(list(csv.reader(read(path).splitlines())) == list(csv.reader(raw.splitlines())),
                    "Existing benchmark differs. Preserve original and reconcile.")
        else:
            save(path, raw)
        assets, initial, weights, lots = zip(*d["benchmark"])
        require(len(set(assets)) == len(assets) and all(isinstance(a,str) and a.strip() and a!="CASH" for a in assets), "Invalid asset names")
        initial, weights, lots = [[number(v) for v in col] for col in (initial,weights,lots)]
        require(min(initial)>0 and min(lots)>0 and min(weights)>=0 and abs(sum(weights)-1)<1e-7,"Invalid benchmark")
        m.update(assets=assets,initial=initial,weights=weights,lots=lots,opening=r["capital"])
        qty = np.zeros(len(assets))
        avg = qty.copy()
        cash = r["capital"]
        prices = np.array(initial)
        save(LOG,table(TH,[]))
    else:
        require(m["stage"] != "new", "Build initial portfolio first")
        assets = m["assets"]
        ledger = list(csv.DictReader(io.StringIO(read(POS))))
        require([a["asset"] for a in ledger] == list(assets)+["CASH"],"Incomplete position ledger")
        qty,avg,marks = [np.array([number(a[k]) for a in ledger[:-1]]) for k in PH[1:4]]
        prices = marks.copy()
        cash = number(ledger[-1]["value"])
    lots = np.array(m["lots"])
    weights = np.array(m["weights"])
    report = []
    if action == "confirm":
        require(pending and d["id"] == pending["id"],"Unknown or settled proposal")
        orders = pending["orders"]
        seen = {a["trade_id"] for a in csv.DictReader(io.StringIO(read(LOG)))}
        lines = []
        for f in d["fills"]:
            a, side, tid = f["asset"], f["side"], f["trade_id"]
            require(tid and tid not in seen and a in orders and side == orders[a][0],"Invalid or duplicate fill")
            seen.add(tid)
            i = assets.index(a)
            n,p,fee = map(number,(f["quantity"],f["price"],f["fee"]))
            require(0<n<=orders[a][1]+1e-9 and p>0 and fee>=0,"Invalid execution")
            orders[a][1] -= n
            amount = n*p
            pnl = 0
            if side == "BUY":
                avg[i] = (qty[i]*avg[i]+amount+fee)/(qty[i]+n)
                qty[i] += n
                cash -= amount+fee
            else:
                pnl = n*(p-avg[i])-fee
                qty[i] -= n
                cash += amount-fee
                if abs(qty[i])<1e-9:
                    qty[i]=avg[i]=0
            prices[i] = p
            lines.append([pending["quarter"],tid,a,side,n,p,amount,pnl,fee])
        require(cash>=-1e-6 and min(qty)>=-1e-9,"Execution inconsistent with available cash/positions")
        append(LOG,table(TH,lines).split("\n",1)[1])
        if d.get("close") is True or all(v[1]<1e-9 for v in orders.values()):
            m.pop("pending")
            if pending["action"] in ("build","rebalance"):
                nav = cash+sum(qty*prices)
                actual = qty*prices/nav
                valid = (sum(actual)>=r["minimum"]-1e-9 and
                         np.all(qty*prices<=r["cap"]+1e-6) and
                         np.all(abs(actual-weights)<=r["dev"]+1e-9))
                m["stage"] = "active" if valid else "repair"
                if valid:
                    m["q"] = pending["quarter"]
                else:
                    m["repair_quarter"] = pending["quarter"]
        executed_nav = cash + sum(qty*prices)
        warnings = []
        if np.any(abs(qty*prices/executed_nav-weights)>r["dev"]+1e-9) or np.any(qty*prices>r["cap"]+1e-6):
            warnings.append("Execution marks outside exposure or deviation limits")
        if any(row[-2] < -r["loss"] for row in lines):
            warnings.append("Realized execution loss exceeds limit")
        output = {"warnings":warnings,"stage":m["stage"],"quarter":m["q"],"pending":m.get("pending")}
    else:
        require(not pending and m["stage"]!="finished","Pending execution or simulation finished")
        require(action in {"new":{"build"},"active":{"news","rebalance","finish"},"repair":{"repair"}}[m["stage"]],"Wrong stage")
        nextq = q+1 if action=="rebalance" else m.get("repair_quarter",q) if action=="repair" else q
        require(nextq<=r["quarters"] and (action!="finish" or q==r["quarters"]),"Wrong quarter")
        ids = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in d["sources"]]
        require(ids and not set(ids)&set(m["seen"]), "Missing or duplicate evidence")
        require(d["analysis"].strip() and d["as_of"].strip(),"Missing analysis or observation time")
        for source,digest in zip(d["sources"],ids):
            archive(source,digest)
        if action!="build":
            require(set(d["prices"])==set(assets),"Current price required for every asset")
            prices = np.array([number(d["prices"][a]) for a in assets])
        require(min(prices)>0,"Invalid price")
        nav = cash+sum(qty*prices)
        folder = Path("data")/f"quarter{nextq}"
        suffix = f"{nextq}" if action!="finish" else f"{q}-final"
        if action in ("rebalance","finish"):
            outcome = d["returns"]
            require(set(outcome)==set(assets)|{"PORTFOLIO"},"Incomplete quarterly returns")
            def snapshot(path,content):
                require(not read(path).strip() or read(path)==content,"Existing data differs: "+str(path))
                save(path,content)
            snapshot(folder/f"outcome{suffix}.csv",table(["asset","quarter_return"],[(a,number(v)) for a,v in outcome.items()]))
            snapshot(folder/f"price-change{suffix}.csv",table(["asset","price","as_of"],zip(assets,prices,[d["as_of"]]*len(assets))))
            actual = nav/m["opening"]-1
            report.append(dict(opening_nav=m["opening"],closing_nav=nav,quarter_return=actual,
                               platform=outcome["PORTFOLIO"],difference=actual-number(outcome["PORTFOLIO"])))
            growth = m.get("benchmark_growth",[1.0]*len(assets))
            m["benchmark_growth"] = [g*(1+number(outcome[a])) for g,a in zip(growth,assets)]
            m["opening"]=nav
        if action in ("news","build"):
            path = Path("data/macro-default.md") if action=="build" else folder/f"macro{q}.md"
            append(path,"\n\n"+d["transcript"]+"\n")
        report.append(dict(quarter=q,as_of=d["as_of"],sources=ids,rules=r,analysis=d["analysis"],
                           current_weights=dict(zip(assets,qty*prices/nav)),nav=nav,cash=cash,
                           unrealized_pnl=dict(zip(assets,qty*(prices-avg)))))
        if action=="finish":
            ret = nav/r["capital"]-1
            bench = sum(weights*(prices/np.array(m["initial"])-1))
            report.append(dict(total_return=ret,fixed_initial_benchmark_price_return=bench,
                               excess_price_return=ret-bench, fixed_benchmark_total_return=float(weights@np.array(m["benchmark_growth"])-1),
                               excess_total_return=float(ret-(weights@np.array(m["benchmark_growth"])-1))))
            output=report[-1]
            m["stage"]="finished"
        else:
            scenarios = np.array([[number(s[a]) for a in assets] for s in d["scenarios"]])
            adverse = np.array([number(d["downside"][a]) for a in assets])
            require(len(scenarios)>0 and min(adverse)>0 and max(adverse)<=1,"Missing downside or scenarios")
            adverse = np.maximum(adverse,-scenarios.min(axis=0))
            require(max(adverse)<=1,"Invalid long-only downside")
            history = d.get("history",[])
            if history:
                samples = np.array([[number(day[a]) for a in assets] for day in history])
                require(len(samples)>len(assets) and np.all(samples.std(axis=0)>0),"Insufficient aligned return history")
                report.append(dict(sample_mean=samples.mean(axis=0).tolist(),sample_covariance=np.atleast_2d(np.cov(samples.T)).tolist(),
                                   correlation=np.atleast_2d(np.corrcoef(samples.T)).tolist(),observations=len(samples)))
            target = optimize(qty*prices,qty/lots,prices*lots,cash,weights,scenarios,adverse,
                              np.maximum(avg-prices,0)*lots,r,action!="news")*lots
            if action == "news" and d.get("hold_reason"):
                values = qty*prices
                require(np.all(values<=r["cap"]+1e-6) and np.all(values*adverse<=r["loss"]+1e-6)
                        and np.all(abs(values/nav-weights)<=r["dev"]+1e-9),"HOLD would violate constraints")
                report.append(dict(hold_reason=d["hold_reason"],optimized_alternative=target.tolist()))
                target = qty.copy()
            orders = {}
            output = []
            for a,delta,p in zip(assets,target-qty,prices):
                if abs(delta)>1e-9:
                    side = "BUY" if delta>0 else "SELL"
                    orders[a]=[side,abs(delta)]
                    output.append([side,a,abs(delta)*p,abs(delta)])
            output.sort(key=lambda x:x[0]=="BUY")
            report.append(dict(scenarios=d["scenarios"],downside=d["downside"],target_weights=dict(zip(assets,target*prices/nav)),
                               weight_change=dict(zip(assets,(target-qty)*prices/nav)),
                               stress_loss=dict(zip(assets,target*prices*adverse)),
                               scenario_profit=(scenarios@(target*prices)).tolist(),orders=output))
            if orders:
                m["pending"]=dict(id=ids[0],action="rebalance" if action=="repair" else action,quarter=nextq,orders=orders)
                if action=="build":
                    m["stage"]="opening"
            else:
                m.update(stage="active",q=nextq)
                output="HOLD"
        name = {"build":"portfolio-building","rebalance":f"quarter{nextq}","finish":"final",
                "repair":f"quarter{nextq}-repair","news":f"quarter{q}-news"}[action]
        append(R/(name+".md"),"\n## "+d["as_of"]+"\n\n"+d["analysis"]+"\n\n```json\n"+
               json.dumps(report,ensure_ascii=False,indent=2)+"\n```\n")
        m["seen"].extend(ids)
    nav = cash+sum(qty*prices)
    save(POS,table(PH,list(zip(assets,qty,avg,prices,qty*prices,qty*prices/nav))+
                   [["CASH",cash,1,1,cash,cash/nav]]))
    save(META,json.dumps(m,ensure_ascii=False,indent=2))
    atomic(JOURNAL,json.dumps(changes))
    recover()
    return output


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices="build news rebalance finish confirm status repair".split())
    parser.add_argument("packet",nargs="?")
    args=parser.parse_args()
    with locked():
        print(json.dumps(run(args.action,json.loads(read(Path(args.packet))) if args.packet else {}),
                         ensure_ascii=False,indent=2))
