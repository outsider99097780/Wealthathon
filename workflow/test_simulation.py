"""All input, reports and ledgers live in a disposable repository."""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import engine as e


class Season(unittest.TestCase):
    def setUp(self):
        home = Path.cwd()
        rules = Path(e.__file__).with_name("constraints.md")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(os.chdir,home)
        os.chdir(tmp.name)
        for name in ("data","workflow","result"):
            Path(name).mkdir()
        shutil.copy(rules,"workflow/constraints.md")
        self.r=e.rules()
        count=int(self.r["capital"]/self.r["cap"])+2
        self.assets=[f"Test{i}" for i in range(count)]
        self.prices={a:100 for a in self.assets}
        self.seq=0

    def packet(self, action):
        self.seq+=1
        source=Path(f"synthetic-{self.seq}.txt")
        source.write_text(str(self.seq))
        return dict(sources=[str(source)],as_of=f"fixture {self.seq}",analysis="Synthetic scenario",
                    prices=self.prices.copy(),transcript="Fixture only",
                    benchmark=[[a,100,1/len(self.assets),1] for a in self.assets],
                    returns=dict.fromkeys(self.assets+["PORTFOLIO"],0),
                    scenarios=[dict.fromkeys(self.assets,0.01)],downside=dict.fromkeys(self.assets,0.02))

    def execute(self):
        pending=e.run("status",{}).get("pending")
        if pending:
            fills=[dict(trade_id=f"{self.seq}-{a}",asset=a,side=s,quantity=n,
                        price=self.prices[a],fee=0) for a,(s,n) in pending["orders"].items()]
            e.run("confirm",dict(id=pending["id"],fills=fills,close=True))

    def test_season(self):
        e.run("build",self.packet("build"))
        self.assertEqual(list(csv.DictReader(e.read(e.LOG).splitlines())),[])
        with self.assertRaises(ValueError):
            e.run("news",self.packet("news"))
        self.execute()
        news=self.packet("news")
        self.assertEqual(e.run("news",news),"HOLD")
        with self.assertRaises(ValueError):
            e.run("news",news)
        bad=self.packet("news")
        bad["prices"].pop(self.assets[0])
        with self.assertRaises(ValueError):
            e.run("news",bad)
        for q in range(2,self.r["quarters"]+1):
            self.prices[self.assets[q%len(self.assets)]]+=1
            e.run("rebalance",self.packet("rebalance"))
            self.execute()
            self.assertEqual(e.run("status",{})["q"],q)
        final=e.run("finish",self.packet("finish"))
        self.assertIn("excess_price_return",final)
        self.assertEqual(e.run("status",{})["stage"],"finished")

    def test_partial_fill_across_processes(self):
        script = Path(e.__file__).resolve()
        def cli(action, packet=None, ok=True):
            args=[sys.executable,str(script),action]
            if packet is not None:
                Path("request.json").write_text(json.dumps(packet))
                args.append("request.json")
            proc=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(proc.returncode==0,ok,proc.stderr)
            return json.loads(proc.stdout) if ok else proc.stderr
        cli("build",self.packet("build"))
        pending=cli("status")["pending"]
        asset,(side,n)=next(iter(pending["orders"].items()))
        fill=dict(asset=asset,side=side,trade_id="partial-1",quantity=1,price=100,fee=0)
        packet=dict(id=pending["id"],fills=[fill],close=False)
        cli("confirm",packet)
        self.assertEqual(cli("status")["pending"]["orders"][asset][1],n-1)
        before=e.read(e.POS),e.read(e.LOG)
        cli("confirm",packet,ok=False)
        self.assertEqual(before,(e.read(e.POS),e.read(e.LOG)))
        cli("confirm",dict(id=pending["id"],fills=[],close=True))
        self.assertEqual(cli("status")["stage"],"repair")

    def test_infeasible_and_replay(self):
        packet=self.packet("build")
        packet["benchmark"]=[[self.assets[0],100,1,1]]
        with self.assertRaises(ValueError):
            e.run("build",packet)
        self.assertFalse(e.META.exists())
        e.atomic(e.JOURNAL,json.dumps({str(e.META):'{"stage":"new","q":1}'}))
        self.assertEqual(e.run("status",{})["stage"],"new")
        self.assertFalse(e.JOURNAL.exists())


if __name__=="__main__":
    unittest.main()
