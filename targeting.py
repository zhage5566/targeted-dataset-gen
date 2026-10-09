# -*- coding: utf-8 -*-
"""按行业与业务场景定向生成；复用核心的去重、随机源及文件流程。"""
import catalogue as C
import scenes as S
from datetime import timedelta


class TargetedMixin:
    def __init__(self, seed, reference_date=None, industries=None, scenario_ids=None):
        super().__init__(seed, reference_date)
        industries = list(C.INDUSTRIES) if industries is None else list(industries)
        if not industries or set(industries) - set(C.INDUSTRIES):
            raise ValueError("请选择至少一个有效行业")
        if scenario_ids is not None and (not scenario_ids or set(scenario_ids) - set(C.BY_ID)):
            raise ValueError("业务场景筛选为空或包含未知场景")
        selected = set(scenario_ids) if scenario_ids is not None else None
        self.targets = [s for s in C.SCENARIOS if s["industry"] in industries and (selected is None or s["id"] in selected)]
        if not self.targets: raise ValueError("所选行业与业务场景没有交集")
        self.industries = industries
        self.agent_targets = [s for s in self.targets if s["id"] in C.AGENT_SCENES]
        self.agent_wants = [t for s, t in [("ecom:after_sales:APPLY_RETURN", "return_refund"), ("ecom:after_sales:APPLY_EXCHANGE", "exchange"), ("ecom:refund:APPLY", "refund_only")] if any(a["id"] == s for a in self.agent_targets)]
        self.agent_progress_only = bool(self.agent_targets) and not self.agent_wants

    def choose_scene(self, task):
        return self.pick(self.targets, task + ":target")

    def values_for(self, scene):
        slots = scene["slots"]
        if scene["industry"] == "ecom":
            return self.slot_values(scene["action"], slots)
        city1, city2 = self.rng.sample(S.CITIES, 2)
        future = (self.today + timedelta(days=self.rng.randint(1, 90))).isoformat()
        historical = self.day()
        industry = scene["industry"]
        reason = self.pick(["行程有变", "出行计划取消", "时间安排冲突"]) if industry == "travel" else self.pick(["时间安排冲突", "个人计划有变", "重复报名"]) if industry == "education" else "业务信息有误"
        values = {
            "account_no": "账户尾号" + f"{self.rng.randrange(10000):04d}", "card_no": "卡尾号" + f"{self.rng.randrange(10000):04d}",
            "bank": self.pick(["示例银行A", "示例银行B", "示例银行C", "示例银行D"]), "currency": self.pick(["人民币", "美元", "欧元"]),
            "recipient": self.pick(["王女士", "李先生", "陈女士"]), "loan_id": self.oid("LN"), "amount": self.amount(),
            "date": historical, "period": self.pick(["三个月", "六个月", "一年", "两年", "三年"]),
            "deposit_type": self.pick(["定期存款", "整存整取存款"]), "fund_product": self.pick(["示例理财A", "示例理财B", "示例理财C"]),
            "policy_id": self.oid("PL"), "insurance_type": self.pick(["意外险", "医疗险", "车险", "财产险"]),
            "departure": city1, "destination": city2, "travel_date": future, "ticket_id": self.oid("TK"),
            "hotel_name": city2 + self.pick(["示例商务酒店", "示例城市酒店", "示例度假酒店"]), "checkin_date": future,
            "nights": str(self.rng.randint(1, 14)), "room_type": self.pick(["大床房", "双床房", "家庭房", "单人房"]),
            "order_id": self.oid(), "pickup": city1 + self.pick(["火车站北广场", "市民中心东门", "机场出发层", "科技园南门"]),
            "reason": reason, "phone": "1" + self.pick("3589") + "****" + f"{self.rng.randrange(10000):04d}",
            "plan": self.pick(["基础流量", "家庭共享", "畅享通话", "学生流量", "日常上网"]), "bill_month": historical[:7],
            "service_id": self.oid("SV"), "address": city1 + "创业路" + str(self.rng.randint(1, 999)) + "号",
            "course_name": self.pick(["Python基础", "商务英语", "数据分析入门", "书法基础", "摄影入门", "绘画基础"]),
            "student": self.pick(["王同学", "李同学", "陈同学", "张同学", "刘同学"]), "class_id": self.oid("CL"),
            "schedule_date": future, "login_method": self.pick(["手机号验证码", "账号密码", "邮箱验证码"]),
        }
        result = {s: values[s] for s in slots}
        self.values.extend(result.values())
        return result

    def intent(self, task):
        scene = self.choose_scene(task)
        if scene["industry"] == "ecom":
            previous = self.scenes
            self.scenes = [s for s in previous if (s[0], s[1]) == (scene["domain"], scene["intent"])]
            try:
                sample = super().intent(task)
            finally: self.scenes = previous
            sample.scene = scene["id"]
            return sample
        vals = self.values_for(scene)
        if self.rng.random() < .45:
            text = scene["natural"].format(**vals)
        else:
            keys = list(vals)
            self.rng.shuffle(keys)
            if self.rng.random() < .25: keys = keys[:self.rng.randint(0, len(keys))]
            vals = {k: vals[k] for k in keys}
            phrases = [self.pick(["{k}是{v}", "{k}：{v}", "{k}为{v}", "{k}填{v}"]).format(k=C.SLOT_LABELS[k], v=vals[k]) for k in keys]
            detail = self.pick(["，", "；", "。", "\n"]).join(phrases)
            action = self.pick(["请帮我{a}", "我想{a}", "需要办理{a}", "咨询一下，如何{a}", "麻烦协助{a}"]).format(a=scene["action"])
            text = self.pick(["{a}。{d}", "{d}。{a}", "{a}\n信息补充：{d}", "{a}，相关信息如下：{d}"]).format(a=action, d=detail) if detail else action
        text = self.style(text)
        ans = {"domain": scene["domain"]} if task == "domain" else {"slots": vals} if task == "slots" else {"domain": scene["domain"], "intent": scene["intent"], "slots": vals}
        return self.single(task, text, ans, scene["id"])

    def dst(self, task):
        scene = self.choose_scene(task)
        dom = C.DOMAINS[scene["domain"]]
        vals = self.values_for(scene)
        keys = list(vals)
        self.rng.shuffle(keys)
        entries = {(dom, "诉求"): {"domain": dom, "slot": "诉求", "value": scene["action"], "active": True}}
        turns = [f"{dom}的诉求是{scene['action']}。"]
        for key in keys:
            slot, value = C.SLOT_LABELS[key], vals[key]
            turns.append(self.pick(["{d}的{s}是{v}。", "关于{d}，{s}：{v}。", "{d}信息补充一下，{s}为{v}。", "我说的是{d}业务，{s}填{v}。", "{d}这边，{s}就按{v}。"]).format(d=dom, s=slot, v=value))
            entries[(dom, slot)] = {"domain": dom, "slot": slot, "value": value, "active": True}
            if self.rng.random() < .32:
                alternative = self.values_for(scene)[key]
                if key in ("departure", "destination"):
                    other = "destination" if key == "departure" else "departure"
                    if alternative == vals.get(other): alternative = self.remember(self.pick([c for c in S.CITIES if c != vals[other]]))
                if alternative != value:
                    turns.append(self.pick(["刚才{d}的{s}说错了，改为{v}。", "更正一下：{d}的{s}以{v}为准。", "{d}的{s}不要用之前那个了，换成{v}。", "确认一下，最终{d}的{s}是{v}。"]).format(d=dom, s=slot, v=alternative))
                    entries[(dom, slot)]["value"] = alternative
                    vals[key] = alternative
            if self.rng.random() < .1:
                turns.append(self.pick(["撤回{d}的{s}信息，先留空。", "{d}的{s}我还没确定，先取消这项。"]).format(d=dom, s=slot))
                entries[(dom, slot)]["active"] = False
        # 让首轮/中途状态也进入数据集；标签只包含截断前实际表达的事实。
        lines = []
        for i, text in enumerate(turns):
            lines.append("用户: " + self.style(text))
            if i < len(turns)-1 and self.rng.random() < .6:
                lines.append("系统: " + self.pick(["收到，请继续补充。", "了解，以您最新说明为准。", "好的，还有需要确认的信息吗？", "我会按您提供的信息记录。", "还有其他信息需要补充吗？", "请继续说明，我在记录。", "好的，已了解您的需求。", "还有需要更正的内容吗？"]))
        values = list(entries.values())
        answer = values if task == "dst_user" else {e["domain"] + "-" + e["slot"]: e["value"] for e in values if e["active"]}
        return self.single(task, "\n".join(lines), answer, scene["id"])

    def clarify(self):
        scene = self.choose_scene("clarify")
        vals = self.values_for(scene)
        fields = list(vals)
        self.rng.shuffle(fields)
        known = fields[:self.rng.randrange(len(fields))]
        missing = [s for s in fields if s not in known]
        fragments = [self.pick(["{k}是{v}", "{k}：{v}", "{k}为{v}"]).format(k=C.SLOT_LABELS[k], v=vals[k]) for k in known]
        detail = self.pick(["，", "；", "\n"]).join(fragments)
        request = self.pick(["我想{a}", "请帮忙{a}", "麻烦协助{a}", "我需要{a}", "咨询一下{a}"]).format(a=scene["action"])
        if detail: request = self.pick(["{r}。{d}", "{d}。{r}", "{r}\n补充：{d}"]).format(r=request, d=detail)
        wanted = "、".join(C.SLOT_LABELS[k] for k in missing)
        question = self.pick(["为帮您{a}，方便提供{m}吗？", "还需要确认{m}，您方便说明吗？", "请补充一下{m}，可以吗？", "方便告知{m}，以便继续核实吗？", "您要{a}，请问{m}是什么？"]).format(a=scene["action"], m=wanted)
        uc = f"用户请求: {request}\n主题: 用户希望{scene['action']}。\n所需信息: 需要补充{wanted}。"
        return self.single("clarify", uc, question, scene["id"])

    def ecom(self):
        if not self.agent_targets: raise ValueError("所选业务没有电商售后 Agent 场景，请选择退货、换货、仅退款或售后进度")
        sample = super().ecom()
        sample.scene = "ecom:agent:" + sample.scene
        return sample
