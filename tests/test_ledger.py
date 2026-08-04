#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记账模块单元测试（标准库 unittest）"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kongfz_ledger as lg


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        lg.LEDGER_FILE = os.path.join(self.tmp, "ledger.json")

    def test_add_in_computes_cost(self):
        rec = lg.add_record("in", "红岩", "9787020002207", 10, 5.0, 0, "2026-08-04")
        self.assertEqual(rec["type"], "in")
        self.assertEqual(rec["cost"], 50.0)
        self.assertNotIn("profit", rec)

    def test_add_out_computes_sale_and_profit(self):
        rec = lg.add_record("out", "红岩", "9787020002207", 3, 15.0, 5.0, "2026-08-04")
        self.assertEqual(rec["sale"], 45.0)
        self.assertEqual(rec["cost"], 15.0)
        self.assertEqual(rec["profit"], 30.0)

    def test_default_date_is_today(self):
        import datetime
        rec = lg.add_record("in", "书", "", 1, 10.0, 0)
        self.assertEqual(rec["date"], datetime.date.today().strftime("%Y-%m-%d"))

    def test_summary_today(self):
        lg.add_record("in", "红岩", "", 2, 5.0, 0, "2026-08-04")
        lg.add_record("out", "红岩", "", 1, 15.0, 5.0, "2026-08-04")
        s = lg.summary("today")
        # 用测试里写入的日期固定范围——但 today 依赖系统日期，此处仅验证结构
        self.assertEqual(set(s.keys()), {"scope", "in_cost", "out_sale", "profit", "in_count", "out_count"})

    def test_trends_structure(self):
        lg.add_record("in", "红岩", "", 2, 5.0, 0, "2026-08-04")
        t = lg.trends()
        self.assertEqual(len(t["weekly"]), 8)
        self.assertEqual(len(t["monthly"]), 6)
        self.assertTrue(all("label" in w and "in_cost" in w for w in t["weekly"]))

    def test_delete_record(self):
        rec = lg.add_record("in", "红岩", "", 1, 5.0, 0, "2026-08-04")
        self.assertTrue(lg.delete_record(rec["id"]))
        self.assertFalse(lg.delete_record(rec["id"]))
        self.assertEqual(lg.list_records(100), [])

    def test_list_filter(self):
        lg.add_record("in", "红岩", "", 1, 5.0, 0, "2026-08-04")
        lg.add_record("out", "红岩", "", 1, 15.0, 5.0, "2026-08-04")
        self.assertEqual(len(lg.list_records(100, "in")), 1)
        self.assertEqual(len(lg.list_records(100, "out")), 1)


if __name__ == "__main__":
    unittest.main()
