# -*- coding: utf-8 -*-
"""可筛选的行业、业务功能和槽位规范；所有业务数据均为合成示例。"""
import scenes as S

INDUSTRIES = {"ecom": "电商", "finance": "金融", "travel": "出行与酒店", "telecom": "通信服务", "education": "教育培训"}
DOMAINS = {"order": "订单", "logistics": "物流", "after_sales": "售后", "refund": "退款", "invoice": "发票",
           "coupon": "优惠券", "product": "商品", "payment": "支付", "member": "会员", "complaint": "投诉", "account": "账户",
           "bank_account": "银行账户", "bank_card": "银行卡", "transfer": "转账", "loan": "贷款", "deposit": "存款",
           "wealth": "理财业务", "insurance": "保险", "flight": "机票", "train": "火车票", "hotel": "酒店", "ride": "网约车",
           "mobile_plan": "手机套餐", "mobile_bill": "话费账单", "broadband": "宽带", "mobile_number": "号码业务",
           "course": "课程", "enrollment": "报名", "class_schedule": "课表", "learning_account": "学习账户"}

ACTION_NAMES = {
    ("order", "QUERY"): "查订单状态", ("order", "CANCEL"): "取消订单", ("order", "MODIFY"): "修改订单信息",
    ("order", "URGE"): "催促发货", ("order", "CONFIRM_RECEIPT"): "确认收货",
    ("logistics", "QUERY"): "查询物流", ("logistics", "URGE"): "催促派送", ("logistics", "EXCEPTION"): "核查物流异常", ("logistics", "REDIRECT"): "修改配送地址",
    ("after_sales", "APPLY_RETURN"): "申请退货退款", ("after_sales", "APPLY_EXCHANGE"): "申请换货", ("after_sales", "APPLY_REPAIR"): "申请维修",
    ("after_sales", "QUERY_PROGRESS"): "查询售后进度", ("after_sales", "CANCEL"): "撤销售后申请",
    ("refund", "QUERY"): "查询退款进度", ("refund", "APPLY"): "申请仅退款", ("refund", "URGE"): "催促退款",
    ("invoice", "APPLY"): "申请发票", ("invoice", "MODIFY"): "修改发票", ("invoice", "QUERY"): "查询发票",
    ("coupon", "QUERY"): "查询优惠券规则", ("coupon", "RECEIVE"): "领取优惠券", ("coupon", "USE_ISSUE"): "核查用券异常",
    ("product", "QUERY"): "咨询商品信息", ("product", "STOCK"): "查询商品库存", ("product", "PRICE"): "查询商品价格",
    ("payment", "FAILED"): "核查支付失败", ("payment", "QUERY"): "查询支付方式", ("payment", "INSTALLMENT"): "咨询分期支付",
    ("member", "QUERY"): "查询会员权益", ("member", "BENEFIT"): "办理积分权益", ("complaint", "COMPLAIN"): "登记投诉",
    ("account", "MODIFY"): "修改账户信息", ("account", "ISSUE"): "核查账户异常",
}
SLOT_LABELS = {"order_id": "订单号", "tracking_no": "快递单号", "product": "商品名称", "product2": "对比商品", "brand": "品牌",
               "city": "城市", "address": "详细地址", "date": "日期", "size": "尺码", "color": "颜色", "phone": "手机号",
               "name": "收货人", "amount": "金额", "payment": "支付方式", "company": "发票抬头", "tax_no": "税号",
               "logistics": "承运商", "reason": "原因", "coupon": "优惠券", "level": "会员等级", "account_no": "脱敏账号",
               "card_no": "脱敏卡号", "bank": "银行", "currency": "币种", "recipient": "收款人", "loan_id": "贷款编号",
               "period": "期限", "deposit_type": "存款类型", "fund_product": "理财产品", "policy_id": "保单编号", "insurance_type": "保险类型",
               "departure": "出发城市", "destination": "目的城市", "travel_date": "出行日期", "ticket_id": "票单编号",
               "hotel_name": "酒店名称", "checkin_date": "入住日期", "nights": "入住晚数", "room_type": "房型", "pickup": "上车地点",
               "plan": "套餐", "bill_month": "账单月份", "service_id": "业务编号", "course_name": "课程名称", "student": "学员称呼",
               "class_id": "班级编号", "schedule_date": "上课日期", "login_method": "登录方式"}

DEFAULT_SLOTS = {"order": ["order_id", "product"], "logistics": ["tracking_no", "city"], "after_sales": ["order_id", "product", "reason"],
                 "refund": ["order_id", "amount", "payment"], "invoice": ["order_id", "company"], "coupon": ["coupon", "product"],
                 "product": ["product", "color"], "payment": ["order_id", "payment"], "member": ["level", "coupon"], "complaint": ["order_id", "reason"], "account": ["phone"]}

SCENARIOS = []
for domain, intent, templates in S.INTENT_SCENES:
    SCENARIOS.append({"id": f"ecom:{domain}:{intent}", "industry": "ecom", "domain": domain, "intent": intent,
                      "action": ACTION_NAMES[(domain, intent)], "slots": DEFAULT_SLOTS[domain], "templates": templates})


def add(industry, domain, intent, action, slots, natural):
    SCENARIOS.append({"id": f"{industry}:{domain}:{intent}", "industry": industry, "domain": domain, "intent": intent,
                      "action": action, "slots": slots, "natural": natural})


add("finance", "bank_account", "QUERY_BALANCE", "查询账户余额", ["account_no", "bank", "currency"], "帮我查一下{bank}账户{account_no}的{currency}余额")
add("finance", "bank_account", "QUERY_TRANSACTIONS", "查询账户流水", ["account_no", "date"], "账户{account_no}在{date}的交易记录帮我看一下")
add("finance", "bank_card", "REPORT_LOSS", "办理银行卡挂失", ["card_no", "bank"], "我的{bank}银行卡{card_no}丢了，我要挂失")
add("finance", "bank_card", "QUERY_STATUS", "查询银行卡状态", ["card_no", "bank"], "查下{bank}的卡{card_no}是否已被冻结")
add("finance", "transfer", "QUERY_PROGRESS", "查询转账进度", ["account_no", "amount", "date"], "{date}从账户{account_no}转出{amount}元，帮我查询到账进度")
add("finance", "transfer", "QUERY_LIMIT", "查询转账限额", ["account_no", "bank"], "我想查询{bank}账户{account_no}的转账限额")
add("finance", "loan", "QUERY_REPAYMENT", "查询还款计划", ["loan_id", "date"], "贷款{loan_id}在{date}需要还多少，帮我查询还款计划")
add("finance", "loan", "QUERY_PREPAYMENT", "查询提前还款流程", ["loan_id", "amount"], "贷款{loan_id}我想提前还{amount}元，怎么办理")
add("finance", "deposit", "QUERY_MATURITY", "查询存款到期日", ["account_no", "deposit_type", "period"], "账户{account_no}的{period}{deposit_type}何时到期")
add("finance", "wealth", "QUERY_REDEMPTION", "查询理财赎回进度", ["fund_product", "amount", "date"], "{date}赎回的{fund_product}，金额{amount}元，帮我查进度")
add("finance", "insurance", "QUERY_POLICY", "查询保单状态", ["policy_id", "insurance_type"], "帮我查一下{insurance_type}保单{policy_id}的状态")
add("finance", "insurance", "QUERY_CLAIM", "查询理赔进度", ["policy_id", "date"], "保单{policy_id}在{date}申请了理赔，想查询处理进度")
add("travel", "flight", "QUERY_FLIGHT", "查询机票", ["departure", "destination", "travel_date"], "想查{travel_date}从{departure}到{destination}的机票")
add("travel", "flight", "REFUND_TICKET", "申请机票退票", ["ticket_id", "reason"], "票单{ticket_id}因为{reason}需要退票")
add("travel", "train", "CHANGE_TICKET", "办理火车票改签", ["ticket_id", "travel_date", "destination"], "火车票{ticket_id}想改成{travel_date}去{destination}的车次")
add("travel", "train", "QUERY_TICKET", "查询火车票", ["departure", "destination", "travel_date"], "帮忙看看{travel_date}从{departure}去{destination}的火车票")
add("travel", "hotel", "QUERY_ROOM", "查询酒店房型", ["hotel_name", "checkin_date", "room_type"], "{hotel_name}在{checkin_date}还有{room_type}吗")
add("travel", "hotel", "CANCEL_BOOKING", "取消酒店预订", ["order_id", "hotel_name", "checkin_date"], "取消{checkin_date}入住{hotel_name}的订单{order_id}")
add("travel", "ride", "QUERY_ORDER", "查询网约车订单", ["order_id", "pickup"], "上车地点{pickup}，订单{order_id}，帮我看看司机到哪了")
add("travel", "ride", "COMPLAIN", "登记网约车投诉", ["order_id", "reason"], "我要投诉订单{order_id}，原因是{reason}")
add("telecom", "mobile_plan", "QUERY_PLAN", "查询套餐", ["phone", "plan"], "手机{phone}的{plan}套餐还有多少流量")
add("telecom", "mobile_plan", "CHANGE_PLAN", "变更套餐", ["phone", "plan"], "号码{phone}想改用{plan}套餐")
add("telecom", "mobile_bill", "QUERY_BILL", "查询话费账单", ["phone", "bill_month"], "帮我查下号码{phone}的{bill_month}账单")
add("telecom", "mobile_bill", "DISPUTE_CHARGE", "核查异常扣费", ["phone", "amount", "bill_month"], "号码{phone}在{bill_month}多扣了{amount}元，帮我核实")
add("telecom", "broadband", "REPORT_FAULT", "报修宽带", ["service_id", "address"], "业务{service_id}的宽带断网了，地址是{address}，需要报修")
add("telecom", "broadband", "QUERY_INSTALLATION", "查询宽带安装进度", ["service_id", "date"], "{date}预约的宽带业务{service_id}何时安装")
add("telecom", "mobile_number", "REPORT_LOSS", "办理号码挂失", ["phone"], "手机卡丢了，帮我挂失号码{phone}")
add("education", "course", "QUERY_COURSE", "查询课程内容", ["course_name"], "我想了解{course_name}课程都学什么")
add("education", "course", "QUERY_PRICE", "查询课程价格", ["course_name"], "{course_name}课程现在的报名费用是多少")
add("education", "enrollment", "QUERY_ENROLLMENT", "查询报名状态", ["course_name", "student", "order_id"], "学员{student}报名了{course_name}，订单{order_id}，帮我查报名状态")
add("education", "enrollment", "CANCEL_ENROLLMENT", "取消课程报名", ["course_name", "order_id", "reason"], "订单{order_id}的{course_name}报名因为{reason}需要取消")
add("education", "class_schedule", "QUERY_SCHEDULE", "查询上课时间", ["class_id", "schedule_date"], "班级{class_id}在{schedule_date}几点上课")
add("education", "class_schedule", "RESCHEDULE", "申请调课", ["class_id", "schedule_date", "student"], "学员{student}想把{class_id}班的课调到{schedule_date}")
add("education", "learning_account", "LOGIN_ISSUE", "核查学习账户登录异常", ["phone", "login_method"], "学习账号绑定{phone}，用{login_method}登不上")

BY_ID = {s["id"]: s for s in SCENARIOS}
AGENT_SCENES = {"ecom:after_sales:APPLY_RETURN", "ecom:after_sales:APPLY_EXCHANGE", "ecom:after_sales:QUERY_PROGRESS", "ecom:refund:APPLY"}
