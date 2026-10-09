# -*- coding: utf-8 -*-
"""场景与词表；不包含随机数全局状态或文件写入。"""


SYS = {
    "intent": '你是一个任务型对话的意图识别与槽位抽取助手。给定一句用户消息，识别其所属领域(domain)、意图(intent)，并抽取其中的槽位(slots，键为槽位名、值为槽位值)。只输出一个 JSON 对象：{"domain":"领域","intent":"意图","slots":{"槽位名":"值"}}。',
    "domain": '你是一个对话领域分类助手。给定一句用户消息，判断它属于哪个领域(domain)。只输出一个 JSON 对象：{"domain":"领域名"}。',
    "dst_user": '你是一个任务型对话的状态跟踪(DST)助手。根据对话历史和当前用户消息，输出当前累积的对话状态(user_state)：用户已表达的「领域-槽位-值」信息。只输出一个 JSON 数组，每个元素为 {"domain":"领域","slot":"槽位","value":"值","active":true/false}。',
    "dst_belief": '你是一个任务型对话的状态跟踪(DST)助手。根据对话历史和当前用户消息，输出当前累积的对话状态(belief_state)：各领域已告知的槽位值。只输出一个 JSON 对象，键为「领域-槽位」，值为槽位值。',
    "clarify": '你是一个澄清问题生成助手。给定用户模糊的初始请求及其主题、所需信息方面，生成一个具体的澄清问题以消除歧义。只输出澄清问题本身。',
    "ecom": '你是电商售后客服助手。根据对话历史和工具返回结果，决定下一步动作：调用某个工具(Action)或直接回复用户。可用工具：query_order_status、check_return_policy、create_after_sales_request。调用工具时输出两行：第一行 `Action: 工具名`，第二行 `Action Input: {"参数":"值"}`。',
}

PRODUCTS = ["无线键盘","蓝牙鼠标","机械键盘","保温杯","运动鞋","连衣裙","手机壳","充电宝","蓝牙耳机",
    "空气炸锅","电饭煲","洗衣液","婴儿奶粉","猫粮","行李箱","台灯","床垫","沙发","书架","卫衣","牛仔裤",
    "手表","平板保护套","数据线","电吹风","剃须刀","加湿器","扫地机器人","智能手环","烤箱","微波炉",
    "电风扇","取暖器","瑜伽垫","哑铃","帐篷","折叠椅","炒锅","刀具套装","洗发水","面膜","口红","眼霜",
    "防晒霜","双肩包","钱包","雨伞","儿童积木","遥控车","滑板车","故事机","点读笔","学习桌","电竞椅",
    "显示器","路由器","移动硬盘","U盘","自拍杆","三脚架","无人机","按摩仪","足浴盆","破壁机","咖啡机",
    "面包机","榨汁杯","电动牙刷","冲牙器","卷发棒","直发梳","美甲灯","香水","精华水","身体乳","护手霜",
    "婴儿车","安全座椅","纸尿裤","湿巾","恒温杯","料理机","电压力锅","豆浆机","除螨仪","挂烫机",
    "颈部按摩仪","筋膜枪","跑步鞋","板鞋","帆布鞋","雪地靴","防晒衣","羽绒服","毛衣","风衣","睡衣",
    "内衣","袜子","棒球帽","围巾","手套","墨镜","老花镜","项链","耳钉","发夹","皮带","拉杆箱",
    "登机箱","收纳箱","置物架","鞋架","衣架","脏衣篮","垃圾桶","拖把","扫把","抹布","垃圾袋",
    "洗洁精","消毒液","纸巾","湿厕纸","洗脸巾","化妆棉","牙线","漱口水","沐浴露","香皂","护发素",
    "染发剂","假发","睫毛夹","美妆蛋","散粉","眉笔","眼线笔","睫毛膏","唇釉","卸妆水","洗面奶"]

BRANDS = ["小米","华为","美的","格力","海尔","苏泊尔","九阳","南极人","恒源祥","三只松鼠","良品铺子",
    "联想","罗技","飞利浦","飞科","安踏","李宁","优衣库","波司登","百丽","自然堂","珀莱雅","薇诺娜","全棉时代"]

CITIES = ["北京","上海","广州","深圳","杭州","成都","武汉","西安","南京","苏州","重庆","天津","长沙",
    "郑州","合肥","青岛","济南","宁波","无锡","佛山","东莞","福州","厦门","昆明","贵阳","南昌","石家庄"]

LOGIS = ["顺丰","中通","圆通","韵达","申通","京东物流","邮政EMS","极兔","德邦","百世"]

REASONS = ["商品破损","发错货了","少发漏发","质量有问题","尺码不合适","颜色不喜欢","与页面描述不符",
    "七天无理由","用着不合适","买多了","重复下单","收到时包装已损坏","功能达不到预期","配件缺失",
    "用过一次就坏了","做工太粗糙","有异味","尺寸比想象中小","色差太大","家里人不同意买"]

SIZES = ["S","M","L","XL","XXL","36码","37码","38码","39码","40码","41码","42码","均码"]

COLORS = ["黑色","白色","灰色","藏青色","酒红色","卡其色","粉色","天蓝色","米白色","军绿色"]

PAYS = ["微信支付","支付宝","银行卡","花呗","白条","信用卡","云闪付"]

LEVELS = ["普通会员","银卡会员","金卡会员","铂金会员","钻石会员"]

COUPONS = ["满199减30","满299减50","满99减10","新人专享券","品类八折券","会员日五折券","满599减100","无门槛5元券"]

PROVINCES = ["广东省","浙江省","江苏省","山东省","四川省","湖北省","湖南省","河南省","福建省","安徽省"]

LOGI_PREFIX = {"顺丰": "SF", "圆通": "YT", "中通": "ZT", "韵达": "YD", "申通": "ST",
               "京东物流": "JD", "邮政EMS": "EMS", "极兔": "JT", "德邦": "DPK", "百世": "BT"}

WEAR_CLOTH = ["连衣裙", "卫衣", "牛仔裤", "外套", "T恤", "风衣", "毛衣", "半身裙"]

WEAR_SHOE = ["运动鞋", "跑步鞋", "板鞋", "帆布鞋", "皮鞋", "靴子"]

CLOTH_SIZES = ["S", "M", "L", "XL", "XXL", "均码"]

SHOE_SIZES = ["36码", "37码", "38码", "39码", "40码", "41码", "42码"]

def build_intent_scenes():
    S = []
    def add(dom, it, tpls):
        S.append((dom, it, tpls))

    add("order", "QUERY", [
        ("帮我查一下订单{order_id}到哪了", ["order_id"]),
        ("我想看看{date}买的{product}发货没有", ["date", "product"]),
        ("查一下我的{product}订单状态", ["product"]),
        ("订单{order_id}现在是什么状态？", ["order_id"]),
        ("你好，帮忙看下我前两天下的{product}单子", ["product"]),
        ("我的订单{order_id}怎么还没动静", ["order_id"]),
        ("帮我看看最近一笔订单的情况", []),
        ("查下{order_id}这单{product}什么时候能到", ["order_id", "product"]),
    ])
    add("order", "CANCEL", [
        ("订单{order_id}我不要了，帮我取消", ["order_id"]),
        ("帮我把刚拍的{product}退掉，还没发货", ["product"]),
        ("取消订单{order_id}，拍错了", ["order_id"]),
        ("我想取消{date}下的那笔订单", ["date"]),
        ("不要了，订单{order_id}麻烦取消一下谢谢", ["order_id"]),
        ("刚下单的{product}能取消吗，还没付款", ["product"]),
    ])
    add("order", "MODIFY", [
        ("订单{order_id}的收货地址帮我改到{city}", ["order_id", "city"]),
        ("我想把{product}换成{color}的", ["product", "color"]),
        ("订单{order_id}尺码拍错了，改成{size}", ["order_id", "size"]),
        ("帮我把订单{order_id}的联系电话改成{phone}", ["order_id", "phone"]),
        ("收货人改成{name}，电话{phone}", ["name", "phone"]),
        ("{product}颜色选错了，想要{color}", ["product", "color"]),
    ])
    add("order", "URGE", [
        ("订单{order_id}都三天了怎么还不发货", ["order_id"]),
        ("催一下我的{product}，急着用", ["product"]),
        ("{date}买的{product}到现在没发货，搞什么", ["date", "product"]),
        ("麻烦帮我催催订单{order_id}", ["order_id"]),
        ("我{product}什么时候才发啊，等不及了", ["product"]),
    ])
    add("order", "CONFIRM_RECEIPT", [
        ("订单{order_id}我已经收到了，帮我确认收货", ["order_id"]),
        ("东西到了，确认一下收货，订单{order_id}", ["order_id"]),
        ("帮我确认收货，{product}已签收", ["product"]),
    ])
    add("logistics", "QUERY", [
        ("帮我查下快递{tracking_no}到哪儿了", ["tracking_no"]),
        ("订单{order_id}的物流信息看一下", ["order_id"]),
        ("我的{product}发的什么快递，到哪了", ["product"]),
        ("查一下{logistics}单号{tracking_no}", ["logistics", "tracking_no"]),
        ("物流好几天没更新了，帮我看看{tracking_no}", ["tracking_no"]),
        ("我买的{product}现在到哪个城市了", ["product"]),
    ])
    add("logistics", "URGE", [
        ("快递{tracking_no}卡在{city}三天了，催一下", ["tracking_no", "city"]),
        ("催催我的包裹，{tracking_no}，着急用", ["tracking_no"]),
        ("{logistics}也太慢了，{tracking_no}什么时候送", ["logistics", "tracking_no"]),
        ("买的{product}一直不派送，麻烦催催", ["product"]),
    ])
    add("logistics", "EXCEPTION", [
        ("快递{tracking_no}显示签收了但我没收到", ["tracking_no"]),
        ("包裹{tracking_no}好像丢了，帮我查查", ["tracking_no"]),
        ("收到的包裹外包装破了，{product}也压坏了", ["product"]),
        ("物流显示已签收，可是我没收到{product}啊", ["product"]),
        ("快递被放到驿站了没通知我，单号{tracking_no}", ["tracking_no"]),
    ])
    add("logistics", "REDIRECT", [
        ("快递{tracking_no}帮我改送到{city}的新地址", ["tracking_no", "city"]),
        ("我搬家了，{tracking_no}能改地址吗", ["tracking_no"]),
        ("包裹别送原地址了，改到{city}{address}", ["city", "address"]),
    ])
    add("after_sales", "APPLY_RETURN", [
        ("{product}我想退货，{reason}", ["product", "reason"]),
        ("订单{order_id}申请退货，{reason}", ["order_id", "reason"]),
        ("刚收到的{product}不满意，怎么退", ["product"]),
        ("我要退货！{product}{reason}，太糟心了", ["product", "reason"]),
        ("帮忙办理一下{order_id}的退货退款", ["order_id"]),
        ("{product}七天无理由退货怎么操作", ["product"]),
    ])
    add("after_sales", "APPLY_EXCHANGE", [
        ("{product}尺码小了，换个{size}的", ["product", "size"]),
        ("订单{order_id}申请换货，{reason}", ["order_id", "reason"]),
        ("{color}不喜欢，帮我换个颜色", ["color"]),
        ("收到的{product}有质量问题，换一个新的", ["product"]),
        ("换货怎么弄？{order_id}这单{reason}", ["order_id", "reason"]),
    ])
    add("after_sales", "APPLY_REPAIR", [
        ("{product}用了两个月就坏了，能保修吗", ["product"]),
        ("订单{order_id}的{product}需要维修", ["order_id", "product"]),
        ("{brand}{product}开不了机，申请售后维修", ["brand", "product"]),
        ("保修期内的{product}故障了，怎么寄修", ["product"]),
    ])
    add("after_sales", "QUERY_PROGRESS", [
        ("我的退货申请{order_id}处理到哪一步了", ["order_id"]),
        ("换货寄回去好几天了，什么时候发新的", []),
        ("售后单{order_id}的进度帮我看下", ["order_id"]),
        ("上周申请的退款怎么还没到账", []),
        ("{product}的售后处理得怎么样了", ["product"]),
    ])
    add("after_sales", "CANCEL", [
        ("售后申请帮我撤销一下，订单{order_id}", ["order_id"]),
        ("退货不想退了，{order_id}取消售后", ["order_id"]),
        ("撤销换货申请，东西我将就用了", []),
    ])
    add("refund", "QUERY", [
        ("退款什么时候到账啊，订单{order_id}", ["order_id"]),
        ("帮我查下{order_id}的退款进度", ["order_id"]),
        ("退的{amount}元怎么还没退回来", ["amount"]),
        ("退款显示成功但我{payment}里没收到", ["payment"]),
    ])
    add("refund", "APPLY", [
        ("订单{order_id}我要申请仅退款，{reason}", ["order_id", "reason"]),
        ("没收到货，申请退款，订单{order_id}", ["order_id"]),
        ("{product}不要了，直接退钱吧", ["product"]),
        ("商家一直没发货，我要退款{amount}元", ["amount"]),
    ])
    add("refund", "URGE", [
        ("退款都五天了还没到账，催一下", []),
        ("{order_id}的退款麻烦加急处理", ["order_id"]),
        ("说好三天退款，都一周了钱呢", []),
        ("催催我的退款，{amount}元，急用", ["amount"]),
    ])
    add("invoice", "APPLY", [
        ("订单{order_id}帮我开张发票", ["order_id"]),
        ("我要开发票，抬头是{company}", ["company"]),
        ("{product}的电子发票开一下，抬头{company}，税号{tax_no}", ["product", "company", "tax_no"]),
        ("帮忙开{amount}元的发票，个人抬头", ["amount"]),
        ("上个月的订单能补开发票吗", []),
    ])
    add("invoice", "MODIFY", [
        ("发票抬头开错了，改成{company}", ["company"]),
        ("订单{order_id}的发票需要换开，税号错了", ["order_id"]),
        ("电子发票麻烦重开一张，抬头改为{company}，税号{tax_no}", ["company", "tax_no"]),
    ])
    add("invoice", "QUERY", [
        ("我的发票开好了吗，订单{order_id}", ["order_id"]),
        ("电子发票发到我邮箱了吗", []),
        ("帮我查下{company}抬头的发票状态", ["company"]),
    ])
    add("coupon", "QUERY", [
        ("我的{coupon}怎么不能用", ["coupon"]),
        ("账户里还有哪些优惠券", []),
        ("{coupon}的使用条件是什么", ["coupon"]),
        ("这张券{date}就过期了吗", ["date"]),
    ])
    add("coupon", "RECEIVE", [
        ("新人优惠券在哪里领", []),
        ("怎么领{coupon}", ["coupon"]),
        ("会员日的券什么时候发放", []),
    ])
    add("coupon", "USE_ISSUE", [
        ("结算时{coupon}抵扣不了怎么回事", ["coupon"]),
        ("满足门槛了为什么{coupon}用不了", ["coupon"]),
        ("优惠券和满减能叠加吗", []),
        ("下单忘了用券，能补吗", []),
    ])
    add("product", "QUERY", [
        ("{brand}{product}有{size}的吗", ["brand", "product", "size"]),
        ("这款{product}是什么材质的", ["product"]),
        ("{product}有{color}吗", ["product", "color"]),
        ("这款{product}适合多大孩子用", ["product"]),
        ("{brand}{product}电池续航多久", ["brand", "product"]),
        ("{product}和{product2}哪个更好", ["product", "product2"]),
        ("这款{product}保修多久", ["product"]),
    ])
    add("product", "STOCK", [
        ("{product}还有货吗", ["product"]),
        ("{brand}{product}{color}什么时候补货", ["brand", "product", "color"]),
        ("{size}的{product}缺货了，还会补吗", ["size", "product"]),
    ])
    add("product", "PRICE", [
        ("这款{product}现在多少钱", ["product"]),
        ("{brand}{product}有活动价吗", ["brand", "product"]),
        ("{product}双十一会降价吗", ["product"]),
        ("买两件{product}能便宜点吗", ["product"]),
    ])
    add("payment", "FAILED", [
        ("用{payment}付款一直失败怎么办", ["payment"]),
        ("订单{order_id}支付时提示异常", ["order_id"]),
        ("扣了{amount}元但订单显示未支付", ["amount"]),
        ("{payment}付不了款，急死人了", ["payment"]),
    ])
    add("payment", "QUERY", [
        ("可以用{payment}付款吗", ["payment"]),
        ("支持货到付款吗", []),
        ("能开{payment}的支付凭证吗", ["payment"]),
    ])
    add("payment", "INSTALLMENT", [
        ("{product}支持花呗分期吗", ["product"]),
        ("{amount}元可以分几期", ["amount"]),
        ("分期付款有手续费吗", []),
    ])
    add("member", "QUERY", [
        ("我现在有多少积分", []),
        ("{level}有什么权益", ["level"]),
        ("我的会员什么时候到期", []),
        ("积分能抵现吗", []),
    ])
    add("member", "BENEFIT", [
        ("积分怎么兑换{coupon}", ["coupon"]),
        ("{level}的专属客服在哪里", ["level"]),
        ("会员生日有什么福利", []),
    ])
    add("complaint", "COMPLAIN", [
        ("我要投诉！{product}{reason}，客服一直不处理", ["product", "reason"]),
        ("{logistics}快递员态度太差了，投诉", ["logistics"]),
        ("投诉商家虚假宣传，{product}与描述完全不符", ["product"]),
        ("你们这售后效率太低了，我要投诉", []),
        ("卖家拒绝我的合理退货，帮我介入处理", []),
    ])
    add("account", "MODIFY", [
        ("绑定手机号换了，帮我改成{phone}", ["phone"]),
        ("收货地址默认改成{city}的那个", ["city"]),
        ("怎么注销账号", []),
        ("实名认证信息能修改吗", []),
    ])
    add("account", "ISSUE", [
        ("账号登不上了，提示密码错误", []),
        ("我的账号被冻结了怎么回事", []),
        ("手机收不到验证码，{phone}", ["phone"]),
    ])
    return S


ISSUE_TYPES = {
    "damaged": ["商品破损", "收到的商品有破损", "包装破损商品压坏"],
    "wrong_item": ["发错货", "收到的不是我拍的商品", "颜色/型号发错"],
    "missing_parts": ["少发漏发", "配件缺失", "数量不对"],
    "quality_issue": ["质量问题", "功能故障", "无法正常使用"],
    "not_as_described": ["与描述不符", "材质与页面宣传不一致", "尺寸与描述不符"],
    "no_reason": ["七天无理由", "不喜欢了", "买多了用不上"],
}

REQ_TYPE_CN = {"refund_only": "仅退款", "return_refund": "退货退款", "exchange": "换货"}

INTENT_SCENES = build_intent_scenes()
