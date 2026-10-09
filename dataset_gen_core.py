# -*- coding: utf-8 -*-
"""电商客服合成数据生成器 v2：局部随机源、输入去重、结构配额、逐条校验。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import sqlite3
import tempfile
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations

import scenes as S
import catalogue as C
from targeting import TargetedMixin

VERSION = "2.0.0"
SYS = dict(S.SYS)
SYS["slots"] = '你是任务型对话的槽位抽取助手。抽取用户明确提供的信息，不推测未提供的值。只输出 JSON 对象：{"slots":{"槽位名":"值"}}。'
TASKS = ("intent", "slots", "domain", "dst_user", "dst_belief", "clarify", "ecom")
DEFAULT_WEIGHTS = dict(zip(TASKS, (16, 12, 4, 28, 10, 8, 22)))
DST = str(Path.home() / "Desktop" / "targeted_dataset_v2.jsonl")
SRC = r"D:\Downloads\merged_all_zh.jsonl"
TARGET = 1024 ** 3


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).digest()


def canonical(text):
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"^(你好呀|你好|您好|客服你好|在吗|打扰一下|哈喽)[，,。\s]*", "", text)
    text = re.sub(r"[，,。.!！?？\s]+(谢谢啦|谢谢|麻烦了|多谢)[。!！?？\s]*$", "", text)
    return re.sub(r"[\s，,。.!！?？;；:：]+", "", text)


@dataclass
class Sample:
    task: str
    obj: dict
    masks: tuple = ()
    scene: str = ""

    @property
    def prompt(self):
        return dumps(self.obj["messages"][:-1])

    @property
    def input_key(self):
        return digest(dumps([{ "role": m["role"], "content": canonical(m["content"]) }
                             for m in self.obj["messages"][:-1]]))

    @property
    def answer(self):
        return self.obj["messages"][-1]["content"]

    @property
    def shape(self):
        text = self.prompt
        for value in sorted(set(str(v) for v in self.masks if v), key=len, reverse=True):
            text = text.replace(value, "<值>")
        text = re.sub(r"(?:EC|AS)-[A-Z0-9-]+|(?:SF|YT|ZT|YD|ST|JD|EMS|JT|DPK|BT)\d+", "<编号>", text)
        text = re.sub(r"\d+(?:\.\d+)?", "<数值>", text)
        return digest(canonical(text))


class BaseGenerator:
    def __init__(self, seed, reference_date=None):
        self.rng = random.Random(seed)
        self.today = date.fromisoformat(reference_date) if reference_date else date.today()
        self.counts = Counter()
        self.values = []
        self.scenes = self._intent_scenes()

    def pick(self, choices, group=None):
        if group is None:
            return self.rng.choice(choices)
        # 随机遍历每个场景，避免独立抽样长期忽略低频场景。
        lowest = min(self.counts[(group, i)] for i in range(len(choices)))
        indexes = [i for i in range(len(choices)) if self.counts[(group, i)] == lowest]
        index = self.rng.choice(indexes)
        self.counts[(group, index)] += 1
        return choices[index]

    def remember(self, value):
        self.values.append(str(value))
        return value

    def oid(self, prefix="EC"):
        return self.remember(prefix + "-" + f"{self.rng.getrandbits(64):016X}")

    def product(self, pool=None):
        return self.remember(self.pick(pool or S.PRODUCTS))

    def amount(self):
        # 分层、长尾金额，避免只有几十个固定价格。
        low, high = self.pick([(990, 9990), (10000, 99900), (100000, 499900)])
        return self.remember(f"{self.rng.randint(low, high) / 100:.2f}")

    def day(self, ago=None):
        return self.remember((self.today - timedelta(days=self.rng.randint(0, 180) if ago is None else ago)).isoformat())

    def _intent_scenes(self):
        scenes = []
        for dom, intent, templates in S.INTENT_SCENES:
            templates = list(templates)
            # 统一易混淆边界：退款进度属于 refund；券的报错属于 USE_ISSUE。
            if (dom, intent) == ("after_sales", "QUERY_PROGRESS"):
                templates = [x for x in templates if "退款怎么还没到账" not in x[0]]
            if (dom, intent) == ("coupon", "QUERY"):
                templates = [x for x in templates if "怎么不能用" not in x[0]]
            scenes.append((dom, intent, templates))
        return scenes

    def style(self, text):
        # 只替换确定保持含义的短语；禁止把陈述“可以”改成“能不能”。
        rules = [("帮我查一下", ["帮我查询", "帮忙查下", "请查询"]),
                 ("麻烦", ["劳烦", "辛苦"]), ("什么时候", ["何时", "啥时候"]),
                 ("我想", ["我希望", "我打算"]), ("怎么", ["如何", "咋"])]
        for source, targets in self.rng.sample(rules, len(rules))[:2]:
            if source in text and self.rng.random() < .35:
                text = text.replace(source, self.pick(targets), 1)
        if self.rng.random() < .2:
            text = self.pick(["你好，", "您好，", "客服你好，"]) + text
        return text

    def slot_values(self, template, slots):
        vals = {}
        if "product" in slots:
            pool = None
            if "size" in slots:
                pool = self.pick([S.WEAR_CLOTH, S.WEAR_SHOE])
            elif any(word in template for word in ("开不了机", "电池续航", "维修", "保修", "故障")):
                pool = ["蓝牙耳机", "电饭煲", "显示器", "路由器", "电动牙刷", "空气炸锅", "台灯"]
            elif "适合多大孩子" in template:
                pool = ["儿童积木", "滑板车", "点读笔", "故事机", "学习桌"]
            vals["product"] = self.product(pool)
        if "size" in slots:
            vals["size"] = self.remember(self.pick(S.SHOE_SIZES if vals.get("product") in S.WEAR_SHOE else S.CLOTH_SIZES))
        if "logistics" in slots or "tracking_no" in slots:
            carrier = self.pick(S.LOGIS)
            if "logistics" in slots:
                vals["logistics"] = self.remember(carrier)
            if "tracking_no" in slots:
                vals["tracking_no"] = self.remember(S.LOGI_PREFIX[carrier] + str(self.rng.randrange(10**11, 10**12)))
        for slot in slots:
            if slot in vals:
                continue
            if slot == "order_id": value = self.oid()
            elif slot == "product2":
                groups = [S.WEAR_SHOE, S.WEAR_CLOTH, ["蓝牙耳机", "无线键盘", "机械键盘", "蓝牙鼠标"],
                          ["空气炸锅", "电饭煲", "烤箱", "微波炉", "电压力锅"], ["保温杯", "恒温杯", "榨汁杯"],
                          ["行李箱", "拉杆箱", "登机箱"], ["洗发水", "护发素", "沐浴露"]]
                group = next((g for g in groups if vals.get("product") in g), None)
                if group is None:
                    group = self.pick(groups)
                    vals["product"] = self.product(group)
                value = self.product([p for p in group if p != vals.get("product")])
            elif slot == "amount": value = self.amount()
            elif slot == "date": value = self.day()
            elif slot == "phone": value = "1" + self.pick("3589") + "****" + f"{self.rng.randrange(10000):04d}"
            elif slot == "name": value = self.pick("王李张刘陈杨赵黄周吴徐孙马") + self.pick(["先生", "女士"])
            elif slot == "company": value = self.pick(S.CITIES) + self.pick(["远航", "云启", "星禾", "锦程", "沐风"]) + self.pick(["科技有限公司", "贸易有限公司", "电子商务有限公司"])
            elif slot == "tax_no": value = "91" + "".join(self.rng.choices("0123456789ABCDEFGHJKLMNPQRTUWXY", k=16))
            elif slot == "address": value = self.pick(["创业路", "文景路", "滨江路", "和平路", "朝阳路"]) + str(self.rng.randint(1, 999)) + "号"
            elif slot == "reason":
                reasons = ["商品破损", "发错货了", "质量有问题", "与页面描述不符", "配件缺失", "色差太大"]
                if vals.get("product") in S.WEAR_CLOTH + S.WEAR_SHOE:
                    reasons += ["尺码不合适", "尺寸比想象中小"]
                value = self.pick(reasons)
            else:
                pools = {"brand": S.BRANDS, "city": S.CITIES, "color": S.COLORS, "payment": S.PAYS,
                         "coupon": S.COUPONS, "level": S.LEVELS}
                if slot not in pools:
                    raise ValueError(f"未知槽位: {slot}")
                value = self.pick(pools[slot])
            vals[slot] = self.remember(value)
        # 按产品类目选择品牌，避免“食品品牌显示器”等随机拼接。
        if "brand" in vals and "product" in vals:
            p = vals["product"]
            if p in S.WEAR_CLOTH + S.WEAR_SHOE: brands = ["安踏", "李宁", "优衣库"]
            elif p in ["蓝牙耳机", "显示器", "路由器", "无线键盘", "机械键盘", "蓝牙鼠标", "手机壳", "移动硬盘"]: brands = ["小米", "华为", "联想", "罗技"]
            else: brands = ["自有品牌", "店铺款"]
            vals["brand"] = self.remember(self.pick(brands))
        return vals

    def intent(self, task):
        dom, intent, templates = self.pick(self.scenes, task + ":scene")
        template, slots = self.pick(templates, task + ":" + dom + intent)
        vals = self.slot_values(template, slots)
        text = template.format(**vals)
        # 将“请求”与“已知信息”组合，改变信息顺序和句法，所有新增槽位均同步标注。
        if self.rng.random() < .65:
            enrich = {
                "order": ["order_id", "product", "date"], "logistics": ["tracking_no", "logistics"],
                "after_sales": ["order_id", "product"], "refund": ["order_id", "amount"],
                "invoice": ["order_id"], "coupon": ["coupon"], "product": ["product"],
                "payment": ["order_id", "payment"], "member": ["level"], "complaint": ["order_id"],
                "account": ["phone"],
            }[dom]
            extra = [k for k in enrich if k not in vals]
            if extra:
                extra = self.rng.sample(extra, self.rng.randint(1, len(extra)))
                add = self.slot_values(template, extra)
                if "product" in add and "size" in vals:
                    add["product"] = self.product(S.WEAR_SHOE if vals["size"] in S.SHOE_SIZES else S.WEAR_CLOTH)
                vals.update(add)
                labels = {"order_id": "订单号", "product": "商品", "date": "下单日期", "tracking_no": "快递单号",
                          "logistics": "承运商", "amount": "涉及金额", "coupon": "券名称", "payment": "支付方式",
                          "level": "会员等级", "phone": "绑定手机号"}
                clauses = [self.pick(["{k}是{v}", "{k}：{v}", "{k}为{v}"]).format(k=labels[k], v=add[k]) for k in extra]
                self.rng.shuffle(clauses)
                sep = self.pick(["，", "；", "。", "\n"])
                detail = sep.join(clauses)
                text = self.pick(["{detail}。{text}", "{text}。补充信息：{detail}", "{text}\n{detail}", "我这边的信息是：{detail}。{text}"]).format(text=text, detail=detail)
        text = self.style(text)
        answer = {"domain": dom} if task == "domain" else {"slots": vals} if task == "slots" else {"domain": dom, "intent": intent, "slots": vals}
        return self.single(task, text, answer, f"{dom}/{intent}")

    def single(self, task, user, answer, scene):
        if not isinstance(answer, str):
            answer = dumps(answer)
        return Sample(task, {"messages": [{"role": "system", "content": SYS[task]},
                       {"role": "user", "content": user}, {"role": "assistant", "content": answer}]}, tuple(self.values), scene)



    def ecom(self):
        issue = self.pick(list(S.ISSUE_TYPES), "ecom:issue")
        issue_cn = self.pick(S.ISSUE_TYPES[issue])
        p, oid = self.product(), self.oid()
        want = self.pick(getattr(self, "agent_wants", None) or list(S.REQ_TYPE_CN), "ecom:request")
        want_cn = S.REQ_TYPE_CN[want]
        scenario = self.pick(["missing_order", "normal", "normal", "normal", "existing", "query_only", "tool_failure"], "ecom:flow")
        if getattr(self, "agent_progress_only", False): scenario = "existing"
        status = self.pick(["pending", "shipped", "delivered", "delivered", "delivered"], "ecom:status")
        days = self.pick([0, 1, 6, 7, 8, 14, 30]) if status == "delivered" else None
        paid = self.pick(["paid", "paid", "paid", "refunded"])
        identity = self.pick(["verified", "required"])
        evidence_required = issue in ("damaged", "quality_issue", "not_as_described")
        evidence = evidence_required and self.rng.random() < .55
        existing = {"request_id": self.oid("AS"), "request_type": want, "status": self.pick(["submitted", "reviewing", "approved"])} if scenario == "existing" else None
        msgs = [{"role": "system", "content": SYS["ecom"]}]
        def add(role, content): msgs.append({"role": role, "content": content})
        def action(tool, data): add("assistant", "Action: " + tool + "\nAction Input: " + dumps(data))
        def result(tool, data, ok=True): add("user", "工具返回: " + dumps({"tool": tool, "ok": ok, "data": data}))
        opening = self.pick(["{p}出现{issue}，我想{want}。", "我收到的{p}{issue}，请协助{want}。", "{issue}，商品是{p}，需要{want}。", "关于{p}的售后：{issue}，希望{want}。", "麻烦核实{p}的{issue}问题，我打算{want}。"]).format(p=p, issue=issue_cn, want=want_cn)
        if getattr(self, "agent_progress_only", False):
            opening = self.pick(["我已有售后申请，请帮我查询处理进度。", "售后申请还没处理完，麻烦查一下当前状态。", "请核实这笔订单已有的售后单状态，先别重复提交。"]) 
        if scenario == "missing_order":
            add("user", self.style(opening))
            add("assistant", self.pick(["请提供订单号，我先核实订单和售后政策。", "方便告知订单号吗？核实后我再为您处理。", "请把对应订单号发我，以便查询。", "了解，请补充这笔订单的订单号。", "我需要先确认订单信息，麻烦提供订单号。", "请问是哪笔订单？收到订单号后我为您核实。 "]).strip())
        else:
            if scenario == "query_only": opening += "先查询政策，不要提交申请。"
            if evidence: opening += "我已上传商品问题照片作为凭证。"
            opening = self.pick(["订单号{oid}。{t}", "{t}。对应订单是{oid}。", "{t}\n订单号：{oid}"]).format(oid=oid, t=opening)
            add("user", self.style(opening))
            action("query_order_status", {"order_id": oid})
            if scenario == "tool_failure":
                result("query_order_status", {"error_code": self.pick(["TIMEOUT", "SERVICE_UNAVAILABLE", "ORDER_NOT_FOUND"])}, False)
                add("assistant", "本次查询未成功，暂时无法确认订单状态。请核对订单号，稍后重试或联系人工客服。")
            else:
                result("query_order_status", {"order_id": oid, "fulfillment_status": status, "payment_status": paid,
                                              "days_since_delivery": days, "identity_verification_status": identity,
                                              "after_sales_request": existing, "item_summary": p})
                if existing:
                    add("assistant", f"订单{oid}已有{want_cn}申请，售后单号{existing['request_id']}，状态为{existing['status']}。无需重复提交。")
                else:
                    if paid != "paid": allowed, code, explanation = [], "ALREADY_REFUNDED", "订单已退款，无法重复申请退款或换货。"
                    elif status != "delivered": allowed, code, explanation = ["refund_only"], "NOT_DELIVERED", "尚未签收，当前仅可申请仅退款。"
                    elif days <= 7: allowed, code, explanation = list(S.REQ_TYPE_CN), "IN_WINDOW", "符合本次工具返回的售后时效。"
                    elif issue != "no_reason" and days <= 30: allowed, code, explanation = ["return_refund", "exchange"], "QUALITY_REVIEW", "问题商品可申请退货退款或换货，需审核凭证。"
                    else: allowed, code, explanation = [], "OUT_OF_WINDOW", "超出本次工具返回的售后时效，需人工核实。"
                    action("check_return_policy", {"order_id": oid, "issue_type": issue})
                    result("check_return_policy", {"order_id": oid, "issue_type": issue, "eligible": bool(allowed),
                           "allowed_request_types": allowed, "reason_code": code, "message": explanation,
                           "evidence_required": evidence_required, "policy_version": "synthetic-v2"})
                    options = "、".join(S.REQ_TYPE_CN[t] for t in allowed)
                    if scenario == "query_only":
                        add("assistant", f"查询结果：{explanation}" + (f"可选方式为{options}。" if allowed else "") + "按您的要求，本次未提交申请。")
                    elif want not in allowed:
                        add("assistant", f"当前无法申请{want_cn}：{explanation}" + (f"可选方式为{options}，请确认是否改用其中一种。" if allowed else "我可协助转人工进一步核实。"))
                    elif identity == "required":
                        add("assistant", f"当前政策支持{want_cn}，但还需要完成身份核验。请通过平台核验流程操作，完成后再提交申请。")
                    elif evidence_required and not evidence:
                        add("assistant", f"政策支持{want_cn}，还需上传商品问题照片作为凭证。收到凭证后才能继续提交。")
                    else:
                        action("create_after_sales_request", {"order_id": oid, "request_type": want, "reason": issue})
                        rid = self.oid("AS")
                        result("create_after_sales_request", {"order_id": oid, "request_type": want, "request_id": rid, "status": "submitted"})
                        add("assistant", f"已提交{want_cn}申请，售后单号{rid}，状态为submitted。请在售后页面查看审核进度。")
        # 同一流程采样不同决策节点，丰富下一步工具调用与直接回复的训练目标。
        endpoints = [i for i, m in enumerate(msgs) if i > 0 and m["role"] == "assistant"]
        if len(endpoints) > 1 and self.rng.random() < .25:
            msgs = msgs[:self.pick(endpoints) + 1]
        return Sample("ecom", {"messages": msgs}, tuple(self.values), f"{scenario}/{issue}/{status}")

    def generate(self, task):
        self.values = []
        if task in ("intent", "slots", "domain"): return self.intent(task)
        if task in ("dst_user", "dst_belief"): return self.dst(task)
        return getattr(self, task)()


class Generator(TargetedMixin, BaseGenerator):
    pass


def validate(sample):
    """拒绝格式、标签、槽位、DST 覆盖、工具前置条件及返回不一致的样本。"""
    msgs = sample.obj.get("messages")
    if not isinstance(msgs, list) or len(msgs) < 3:
        raise ValueError("messages 格式错误")
    if msgs[0] != {"role": "system", "content": SYS[sample.task]} or msgs[-1]["role"] != "assistant":
        raise ValueError("系统提示词或末轮角色错误")
    previous = "system"
    for m in msgs[1:]:
        if m.get("role") not in ("user", "assistant") or m["role"] == previous or not isinstance(m.get("content"), str) or not m["content"].strip():
            raise ValueError("消息角色或内容错误")
        previous = m["role"]
        if re.search(r"\{(?:product|reason|date|order_id|size)\}", m["content"]):
            raise ValueError("存在未填充占位符")
    uc, ac = msgs[1]["content"], sample.answer
    if sample.task in ("intent", "slots", "domain"):
        ans = json.loads(ac)
        domains = {x["domain"] for x in C.SCENARIOS}
        if sample.task != "slots" and ans.get("domain") not in domains: raise ValueError("领域不在词表中")
        expected_scene = C.BY_ID.get(sample.scene)
        if expected_scene and sample.task != "slots":
            if ans.get("domain") != expected_scene["domain"] or (sample.task == "intent" and ans.get("intent") != expected_scene["intent"]):
                raise ValueError("标签与定向业务场景不一致")
        if sample.task in ("intent", "slots"):
            if sample.task == "intent" and (ans["domain"], ans.get("intent")) not in {(s["domain"], s["intent"]) for s in C.SCENARIOS}: raise ValueError("非法意图")
            expected = {"slots"} if sample.task == "slots" else {"domain", "intent", "slots"}
            if set(ans) != expected or not isinstance(ans["slots"], dict): raise ValueError("槽位结构错误")
            if any(not v or v not in uc for v in ans["slots"].values()): raise ValueError("槽位值未出现在话术中")
            if "product" in ans["slots"] and "size" in ans["slots"]:
                p, size = ans["slots"]["product"], ans["slots"]["size"]
                pool = S.SHOE_SIZES if p in S.WEAR_SHOE else S.CLOTH_SIZES if p in S.WEAR_CLOTH else []
                if size not in pool: raise ValueError("商品与尺码不匹配")
        elif set(ans) != {"domain"}: raise ValueError("领域标签结构错误")
    elif sample.task in ("dst_user", "dst_belief"):
        ans = json.loads(ac)
        entries = ans if sample.task == "dst_user" else [{"domain": k.split("-", 1)[0], "slot": k.split("-", 1)[1], "value": v, "active": True} for k, v in ans.items()]
        keys = set()
        for e in entries:
            if set(e) != {"domain", "slot", "value", "active"} or type(e["active"]) is not bool: raise ValueError("DST 结构错误")
            key = (e["domain"], e["slot"])
            if key in keys: raise ValueError("DST 槽位重复")
            keys.add(key)
            dom, slot = re.escape(e["domain"]), re.escape(e["slot"])
            scoped = re.compile(rf"(?:{dom}的{slot}|关于{dom}，{slot}|{dom}信息补充一下，{slot}|{dom}业务，{slot}|{dom}这边，{slot})")
            matching = [line for line in uc.splitlines() if line.startswith("用户:") and scoped.search(line)]
            if not matching or not e["value"] or e["value"] not in "\n".join(matching): raise ValueError("DST 值无用户证据")
            last = matching[-1]
            withdrawn = "撤回" in last or "先取消这项" in last
            if e["active"] == withdrawn or (e["active"] and e["value"] not in last): raise ValueError("DST 最新状态错误")
    elif sample.task == "clarify":
        missing = uc.split("所需信息: 需要补充", 1)[-1].rstrip("。")
        if not ac.endswith("？") or any(field not in ac for field in missing.split("、")): raise ValueError("澄清问题遗漏必要信息")
    else:
        validate_ecom(msgs)
    return True


def validate_ecom(msgs):
    order = policy = pending = created = None
    user_history = ""
    for m in msgs[1:]:
        text = m["content"]
        if m["role"] == "user" and not text.startswith("工具返回: "):
            user_history += text
        elif m["role"] == "assistant" and text.startswith("Action: "):
            match = re.fullmatch(r"Action: (\w+)\nAction Input: (.+)", text)
            if not match: raise ValueError("工具调用格式错误")
            tool, raw = match.groups()
            params = json.loads(raw)
            schemas = {"query_order_status": {"order_id"}, "check_return_policy": {"order_id", "issue_type"},
                       "create_after_sales_request": {"order_id", "request_type", "reason"}}
            if tool not in schemas or set(params) != schemas[tool] or params["order_id"] not in user_history: raise ValueError("工具参数错误或缺少用户订单号")
            if tool != "query_order_status" and (not order or params["order_id"] != order["order_id"]): raise ValueError("未经订单核实调用售后工具")
            issue = params.get("issue_type", params.get("reason"))
            if issue and (issue not in S.ISSUE_TYPES or not any(t in user_history for t in S.ISSUE_TYPES[issue])): raise ValueError("售后原因无用户证据")
            if tool == "create_after_sales_request":
                if not policy or not policy["eligible"] or params["request_type"] not in policy["allowed_request_types"]: raise ValueError("违反工具返回的政策")
                if order["identity_verification_status"] != "verified" or order["after_sales_request"]: raise ValueError("身份未核验或重复创建")
                if policy["evidence_required"] and "已上传商品问题照片" not in user_history: raise ValueError("缺少问题凭证")
                if "不要提交申请" in user_history: raise ValueError("未获提交授权")
            pending = (tool, params)
        elif m["role"] == "user" and text.startswith("工具返回: "):
            ret = json.loads(text[len("工具返回: "):])
            if not pending or ret.get("tool") != pending[0] or type(ret.get("ok")) is not bool: raise ValueError("工具返回与调用不对应")
            data = ret["data"]
            if ret["ok"]:
                if data.get("order_id") != pending[1]["order_id"]: raise ValueError("工具返回订单号不一致")
                if ret["tool"] == "query_order_status":
                    order = data
                    if order["fulfillment_status"] != "delivered" and order["days_since_delivery"] is not None: raise ValueError("未签收却有签收天数")
                elif ret["tool"] == "check_return_policy":
                    policy = data
                    if bool(data["allowed_request_types"]) != data["eligible"]: raise ValueError("政策可选类型与资格矛盾")
                    if order["payment_status"] == "refunded" and data["eligible"]: raise ValueError("已退款订单仍获资格")
                else: created = data
            pending = None
        elif m["role"] == "assistant":
            if ("已提交" in text or "申请成功" in text) and not created: raise ValueError("无成功工具返回却声称提交")
            if created and created["request_id"] not in text: raise ValueError("最终回复未引用真实售后单")


class Deduper:
    def __init__(self, path, shape_limit):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS samples (task TEXT, prompt BLOB, answer BLOB, PRIMARY KEY(task,prompt)) WITHOUT ROWID")
        self.db.commit()
        self.shapes = Counter()
        self.shape_limit = shape_limit

    def accept(self, sample):
        key = sample.input_key
        try:
            label = digest(dumps(json.loads(sample.answer)))
        except ValueError:
            label = digest(sample.answer.strip())
        prior = self.db.execute("SELECT answer FROM samples WHERE task=? AND prompt=?", (sample.task, key)).fetchone()
        if prior:
            return "duplicate" if prior[0] == label else "conflict"
        shape = (sample.task, sample.shape)
        if self.shapes[shape] >= self.shape_limit: return "structure_limit"
        self.db.execute("INSERT INTO samples VALUES (?,?,?)", (sample.task, key, label))
        self.shapes[shape] += 1
        return None

    def close(self):
        self.db.commit()
        self.db.close()


def main(dst=DST, target_bytes=TARGET, seed=None, src=SRC, weights_override=None,
         include_original=False, progress_cb=None, stop_event=None, shape_limit=200,
         history_path=None, reference_date=None, industries=None, scenario_ids=None):
    if isinstance(target_bytes, bool) or not isinstance(target_bytes, int) or target_bytes <= 0: raise ValueError("目标字节数必须为正整数")
    if not isinstance(shape_limit, int) or not 1 <= shape_limit <= 100000: raise ValueError("相似结构上限应为 1–100000")
    weights = dict(DEFAULT_WEIGHTS)
    if weights_override is not None:
        if set(weights_override) - set(TASKS): raise ValueError("存在未知任务")
        weights.update(weights_override)
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in weights.values()) or not sum(weights.values()) > 0:
        raise ValueError("任务权重必须有限、非负，且至少启用一项")
    seed = secrets.randbits(64) if seed is None else int(seed)
    gen = Generator(seed, reference_date, ["ecom"] if industries is None else industries, scenario_ids)
    if not gen.agent_targets:
        weights["ecom"] = 0
    active = [k for k in TASKS if weights[k] > 0]
    if not active: raise ValueError("请选择适用于当前行业与业务场景的任务")
    shares = {k: weights[k] / sum(weights.values()) for k in active}
    dst = str(Path(dst).expanduser().resolve())
    if Path(dst).suffix.lower() != ".jsonl": raise ValueError("输出文件请使用 .jsonl 扩展名")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    if src and Path(src).resolve() == Path(dst): raise ValueError("输出文件不能覆盖原始样本文件")
    if history_path and Path(history_path).resolve() in (Path(dst), Path(dst + ".quality.json"), Path(str(src)).resolve()): raise ValueError("历史索引路径不能与数据文件相同")
    if include_original and (not src or not Path(src).is_file()): raise ValueError("选择的原始样本文件不存在")
    stats, byte_stats, rejects, scene_stats, errors = Counter(), Counter(), Counter(), Counter(), Counter()
    written = original_count = attempts = consecutive_rejections = 0
    stopped = False
    start = last_progress = time.monotonic()
    report_path = dst + ".quality.json"
    temp = tempfile.TemporaryDirectory(prefix="ecom-dedup-")
    if history_path:
        Path(history_path).parent.mkdir(parents=True, exist_ok=True)
    deduper = Deduper(history_path or str(Path(temp.name) / "index.sqlite3"), shape_limit)
    def notify(message):
        if progress_cb: progress_cb(written, target_bytes, message)
    notify(f"随机种子：{seed}；参考日期：{gen.today.isoformat()}；逐条校验 + 输入去重 + 结构上限 {shape_limit}")
    try:
        # 仅在成功结束或主动停止后替换目标，异常不会破坏已存在的数据集。
        fd, staging = tempfile.mkstemp(prefix=Path(dst).stem + "-", suffix=".partial", dir=Path(dst).parent)
        with os.fdopen(fd, "wb", buffering=1024*1024) as out:
            def emit(sample, original=False):
                nonlocal written, original_count
                validate(sample)
                reason = deduper.accept(sample)
                if reason:
                    rejects[reason] += 1
                    return False
                blob = (dumps(sample.obj) + "\n").encode("utf-8")
                out.write(blob)
                written += len(blob)
                byte_stats[sample.task] += len(blob)
                stats[sample.task] += 1
                scene_stats[sample.task + ":" + sample.scene] += 1
                if original: original_count += 1
                return True
            if include_original and "ecom" in active:
                notify("扫描原始文件，只混入通过相同校验的售后样本…")
                with open(src, encoding="utf-8-sig") as source:
                    for line in source:
                        if stop_event is not None and stop_event.is_set(): stopped = True; break
                        if written >= target_bytes or byte_stats["ecom"] >= target_bytes * shares["ecom"] * .2: break
                        try:
                            obj = json.loads(line)
                            if obj.get("messages", [{}])[0].get("content") != SYS["ecom"]: continue
                            if {s["id"] for s in gen.agent_targets} != C.AGENT_SCENES:
                                content = "\n".join(m["content"] for m in obj["messages"])
                                requested = {k for k, cn in S.REQ_TYPE_CN.items() if cn in content}
                                if gen.agent_progress_only:
                                    scoped = '"after_sales_request"' in content and '"request_id"' in content
                                else:
                                    scoped = bool(requested) and requested <= set(gen.agent_wants)
                                if not scoped:
                                    rejects["original_out_of_scope"] += 1
                                    continue
                            emit(Sample("ecom", obj, (), "original"), True)
                        except (ValueError, KeyError, TypeError, IndexError) as exc:
                            rejects["original_invalid"] += 1
                notify(f"原始样本通过校验并混入 {original_count} 条")
            while written < target_bytes and not stopped:
                if stop_event is not None and stop_event.is_set(): stopped = True; break
                # 选择当前字节预算完成比例最低的任务，修正长短样本导致的配比偏移。
                ratios = {k: byte_stats[k] / shares[k] for k in active}
                floor = min(ratios.values())
                pool = [k for k in active if ratios[k] <= floor + 4096]
                task = gen.pick(pool)
                sample = gen.generate(task)
                attempts += 1
                try:
                    accepted = emit(sample)
                except (ValueError, KeyError, TypeError, IndexError) as exc:
                    errors[str(exc)] += 1
                    raise RuntimeError(f"生成器校验失败 [{task}]：{exc}") from exc
                if accepted: consecutive_rejections = 0
                else: consecutive_rejections += 1
                if consecutive_rejections >= 20000:
                    raise RuntimeError("当前去重/结构限制下连续 20000 次无新样本。请增大结构上限、减少目标大小或更换历史索引。")
                now = time.monotonic()
                if now - last_progress >= .8:
                    notify(f"{written/1048576:.1f} MB / {sum(stats.values())} 条；过滤 {sum(rejects.values())} 条；{written/max(now-start,.001)/1048576:.2f} MB/s")
                    last_progress = now
            out.flush()
            os.fsync(out.fileno())
        os.replace(staging, dst)
        deduper.db.commit()
        report = {"version": VERSION, "dst": dst, "size": written, "stats": dict(stats), "bytes_by_task": dict(byte_stats),
                  "byte_shares": {k: round(byte_stats[k] / max(written, 1), 6) for k in active}, "requested_shares": shares,
                  "seed": seed, "reference_date": gen.today.isoformat(), "stopped": stopped, "dup": rejects["duplicate"],
                  "industries": gen.industries, "scenario_ids": [s["id"] for s in gen.targets],
                  "rejected": dict(rejects), "validation_errors": dict(errors), "attempts": attempts, "original_count": original_count,
                  "shape_limit": shape_limit, "distinct_shapes": {k: sum(1 for t, _ in deduper.shapes if t == k) for k in active},
                  "max_shape_frequency": {k: max((n for (t, _), n in deduper.shapes.items() if t == k), default=0) for k in active},
                  "scene_counts": dict(scene_stats), "history_path": str(history_path) if history_path else None,
                  "seconds": round(time.monotonic()-start, 3), "report_path": report_path,
                  "note": "本报告衡量格式、标签一致性与模板多样性；合成样本不等同于真实业务数据，synthetic-v2 为模拟工具政策。"}
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        notify(f"{'已停止并保存' if stopped else '完成'}：{sum(stats.values())} 条，质量报告：{report_path}")
        return report
    except Exception as exc:
        # 回滚尚未提交的去重记录，保留异常前的临时输出便于排查。
        deduper.db.rollback()
        failure = {"error": str(exc), "partial_path": staging if "staging" in locals() else None,
                   "seed": seed, "size": written, "stats": dict(stats), "rejected": dict(rejects),
                   "validation_errors": dict(errors), "history_committed": False}
        try:
            Path(dst + ".failed-report.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError: pass
        raise
    finally:
        deduper.close()
        temp.cleanup()


def cli():
    parser = argparse.ArgumentParser(description="电商客服数据集生成器 v2")
    parser.add_argument("--dst", default=DST)
    parser.add_argument("--mb", type=float, default=100)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--shape-limit", type=int, default=200)
    parser.add_argument("--history")
    parser.add_argument("--reference-date", help="YYYY-MM-DD，重现数据时使用报告中的日期")
    parser.add_argument("--industries", default="ecom", help="逗号分隔：ecom,finance,travel,telecom,education")
    parser.add_argument("--scenarios", help="逗号分隔的业务场景 ID，使用 --list-scenes 查看")
    parser.add_argument("--tasks", help="逗号分隔的任务；留空采用默认配比")
    parser.add_argument("--list-scenes", action="store_true")
    args = parser.parse_args()
    if args.list_scenes:
        for s in C.SCENARIOS: print(s["id"], C.INDUSTRIES[s["industry"]], s["action"])
        return
    if not math.isfinite(args.mb) or args.mb <= 0: parser.error("--mb 必须为有限正数")
    if args.tasks and set(args.tasks.split(",")) - set(TASKS): parser.error("--tasks 包含未知任务")
    main(dst=args.dst, target_bytes=int(args.mb*1048576), seed=args.seed, shape_limit=args.shape_limit,
         history_path=args.history, reference_date=args.reference_date,
         industries=args.industries.split(","), scenario_ids=args.scenarios.split(",") if args.scenarios else None,
         weights_override={k: 1 if k in args.tasks.split(",") else 0 for k in TASKS} if args.tasks else None,
         progress_cb=lambda written, total, text: print(text, flush=True))


if __name__ == "__main__":
    cli()
