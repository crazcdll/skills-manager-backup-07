constant {
  number('Module_Gap') {{ 8 }}
  number('Module_BorderRadius') {{ 12 }}
  object('baseInfo') {{
    // 对 PAGE_QUERY 的兜底兼容处理，参考
    // https://km.sankuai.com/collabpage/2704879968

    // 类型转换
    def convertToBoolean(data) {
        return data == true || data == 'true' || (data != null && data != '0' && data != '' && data != 'false')
    }

    // 容器已经自动解码一次了。
    // 但是有些业务传参会编码两次，因此我们需要多解码一次。
    // java 二次解码会把 + 换成空格；
    // 另外，二次解码 '100%' 这种，解码会报错，需要返回原始值；

    def safeDecode = { String s ->
      if (!s) return null
      // 如果没有二次编码，不需要再次解码
      if (s.indexOf('%') == -1) return s
      // 把 + 号替换为特殊字符，避免 java 解码替换为空格
      def tmp = s.replaceAll("%2B", "__DUO__PLUS__").replaceAll("\\+", "__DUO__PLUS__")
      def res = DF.decodeURL(tmp)
      // 如果解码失败，说明不是编码后的字符串，返回原始值
      if (!res) return s
      // 还原 + 号
      return res.replaceAll("__DUO__PLUS__", "+")
    }

    def isMRN = COMMON_PARAMS.systemInfo?.isMRN

    // ======= 境内、境外
    def bizType = PAGE_QUERY.biz_type
      ? (int) DF.toNumber(PAGE_QUERY.biz_type)
      : (PAGE_QUERY.oh_room_price_total ? 2 : 1)
    def isOversea = bizType == 2
    def isInland = !isOversea
    def isInland_ZL = bizType == 3

    // 境外需要先decodeURL
    def extraMRNParamsStr = PAGE_QUERY.extra_params_to_mrn
    if (isOversea && extraMRNParamsStr) {
      extraMRNParamsStr = safeDecode(PAGE_QUERY.extra_params_to_mrn)
    }
    def extraMRNParams = extraMRNParamsStr
      ? DF.jsonParse(extraMRNParamsStr) ?: [:]
      : [:]

    def oh_cancel_typeForPreview = COMMON_PARAMS.isPreview ? (safeDecode(PAGE_QUERY.oh_cancel_type) ?: '') : null
    def oh_propagateDataFromDetailForPreview = COMMON_PARAMS.isPreview ? safeDecode(extraMRNParams.oh_propagateDataFromDetail) : null

    def Incentive_Label = extraMRNParams?.Incentive_Label

    def Incentive_Label_text = extraMRNParams?.Incentive_Label_text

    def have_price_lable = extraMRNParams?.have_price_lable

    def price_lable_text = extraMRNParams?.price_lable_text

    def poiId = extraMRNParams?.poiId

    def shopUuid = extraMRNParams?.shopuuid

    def poiCityID = PAGE_QUERY.poi_city_id ?: extraMRNParams?.poi_city_id ?: PAGE_QUERY?.city_id ?: PAGE_QUERY?.cityId ?: ''

    def channelCityID = extraMRNParams?.channelCityId ?: extraMRNParams?.channelCityID ?: ''

    def conId = PAGE_QUERY?.con_id ?: PAGE_QUERY?.conId ?: PAGE_QUERY?.conid ?: ''

    // spu套餐id
    def spuId = (long) DF.toNumber(PAGE_QUERY.spuId ?: PAGE_QUERY.spuid)

    def isLowestPrice = convertToBoolean(PAGE_QUERY?.is_lowest_price ?: PAGE_QUERY?.isLowestPrice ?: PAGE_QUERY?.is_lowestPrice) ?: false

    // ======= 入住、离店时间
    def formatDate = { Long timestamp -> timestamp ? new Date(timestamp).format("yyyy-MM-dd") : null }
    def createDate = { String date ->
      try {
        def sdf = new java.text.SimpleDateFormat("yyyy-MM-dd")
        return sdf.parse(date)
      } catch(e) {
        return null
      }
    }
    def parseDateToTimestamp = { String date ->
      if (!date) return null
      // 判断是否为毫秒时间戳字符串
      if (date.matches(/^\d+$/)) {
        return (long) DF.toNumber(date)
      } else {
        def dateObj = createDate(date)
        return dateObj?.getTime()
      }
    }
    def checkinDate = parseDateToTimestamp(PAGE_QUERY.checkinDate ?: PAGE_QUERY.checkindate ?: PAGE_QUERY.checkin ?: PAGE_QUERY.checkInDate)
    def checkoutDate = parseDateToTimestamp(PAGE_QUERY.checkoutDate ?: PAGE_QUERY.checkoutdate ?: PAGE_QUERY.checkout ?: PAGE_QUERY.checkOutDate)
    def checkin = formatDate(checkinDate)
    def checkout = formatDate(checkoutDate)

    // 房间数 兜底1
    def roomNum = (int) DF.toNumber(PAGE_QUERY.room_num) ?: 1
    if (isOversea && extraMRNParams ) {
      roomNum = (int) DF.toNumber(extraMRNParams?.roomNumbers) ?: 1
    }

    // 成人数量
    def defaultAdultNum = !isMRN && isOversea ? 1 : 2
    def adultNum = (int) DF.toNumber(PAGE_QUERY.adult_num ?: PAGE_QUERY.adultNum ?: PAGE_QUERY.adultnum ?: PAGE_QUERY.adultCount ?: PAGE_QUERY.roomDefaultAdult ?: defaultAdultNum)
    if (isInland && (adultNum <= 0 || adultNum > 10)) adultNum = 2
    // 儿童年龄数组
    def childAgeStr = safeDecode(PAGE_QUERY.child_age) ?: safeDecode(PAGE_QUERY.childrenAge) ?: PAGE_QUERY.child_age ?: PAGE_QUERY.childrenAge
    def childAge = (childAgeStr && childAgeStr != 'null') ? childAgeStr.split(',').collect({ (int) DF.toNumber(it) }) : []
    // 儿童数量
    def childNum = childAge?.size()
    if (!isMRN && isOversea) {
      childNum = PAGE_QUERY.childCount ?: 0
    }

    // 改签场景
    def isReschedule = isOversea ? extraMRNParams?.is_reschedule : convertToBoolean(PAGE_QUERY.is_reschedule)
    // 旧订单id 删除兜底-1逻辑
    def oldOrderId = (isOversea ? extraMRNParams?.old_order_id : PAGE_QUERY.old_order_id)

    // 是否来自一键续住
    def isQuickExtension = convertToBoolean(PAGE_QUERY.is_quick_extension ?: PAGE_QUERY.is_renew_order ?: PAGE_QUERY.continueLiveOrder)
    // 续住订单号 删除兜底0逻辑
    def continueLiveOrderId = PAGE_QUERY.continueLiveOriginOrderId

    // 店内服务续住房间号
    def roomNo = extraMRNParams?.roomNo ?: ''

    def ctPoi = PAGE_QUERY.ct_poi ?: PAGE_QUERY.ctPoi
    def queryId = PAGE_QUERY.query_id ?: extraMRNParams?.query_id

    def retainWithBlindBoxDiscount = convertToBoolean(PAGE_QUERY.retainWithBlindBoxDiscount)

    def coreSearchNoFixedAd = convertToBoolean(PAGE_QUERY.coreSearchNoFixedAd)

    def propagate = PAGE_QUERY.propagate ?: PAGE_QUERY.propagateData ?: PAGE_QUERY.propagatedata ?: PAGE_QUERY.ohPropagateData

    def applyId = extraMRNParams?.applyId ?: ""
    def isReceiveRedPacketSucceed = convertToBoolean(PAGE_QUERY.isReceiveRedPacketSucceed)

    // 超团场景类型
    def superDealSceneType = (int) DF.toNumber(PAGE_QUERY.superDealSceneType ?:PAGE_QUERY.superdealscenetype ?: 0)
    if (isOversea && extraMRNParams?.oh_entrance == 1001) {
      superDealSceneType = 1
    }
    // 超团券批次id
    def superDealApplyId = PAGE_QUERY.superDealApplyId ?: PAGE_QUERY.superdealapplyid
    // 超团立即预订
    def superDealReservationType = PAGE_QUERY.superDealReservationType ?: PAGE_QUERY.superdealreservationtype
    // 是否是领券订
    def receiveRedPacket = PAGE_QUERY.receiveRedPacket
    // 是否线下业务
    def fromOffline = extraMRNParams?.fromOffline
    // 线下库存
    def underLineShopSell = extraMRNParams?.underLineShopSell
    // 原始商品状态
    def originGoodsStatus = extraMRNParams?.originGoodsStatus
    // 特殊渠道类型
    def specialChannel = extraMRNParams?.specialChannel
    // 线下来源类型
    def offlineSource = extraMRNParams?.offlineSource
    // 盲盒来源类型
    def blindBoxSource = extraMRNParams?.blindBoxSource

    //兼容小程序跳链字段
    if (!isMRN && !extraMRNParams) {
      fromOffline = convertToBoolean(PAGE_QUERY.fromOffline) ?: false
      underLineShopSell = convertToBoolean(PAGE_QUERY.underLineShopSell) ?: false
      originGoodsStatus = PAGE_QUERY.originGoodsStatus ? (int) DF.toNumber(PAGE_QUERY.originGoodsStatus ?: 0) : null
      specialChannel = PAGE_QUERY.specialChannel ? (int) DF.toNumber(PAGE_QUERY.specialChannel ?: 0) : null
      offlineSource = PAGE_QUERY.offlineSource ? (int) DF.toNumber(PAGE_QUERY.offlineSource ?: 0) : null
      blindBoxSource = PAGE_QUERY.blindBoxSource
      poiId = PAGE_QUERY.poiId ? (int) DF.toNumber(PAGE_QUERY.poiId) : null
      // 小程序如果没有channelCityID的时候用首页选择城市ID兜底
      channelCityID = COMMON_PARAMS.cityInfo?.cityId ?: ''
    }

    // 线下vip 3大美卡，4线下活动专项价，5住吧屏，6AI管家
    def isOfflineVIP = !!fromOffline && (offlineSource == 3 || offlineSource == 4 || offlineSource == 5 || offlineSource == 6);
    // 进入新提单页渠道标识。1：表示从猜你喜欢频道进入，不区分小程序和客户端
    def poiChannelScene = PAGE_QUERY.poiChannelScene ? (int) DF.toNumber(PAGE_QUERY.poiChannelScene) : null

    return [
      bizType: bizType,
      isOversea: isOversea,
      isInland: isInland,
      isInland_ZL: isInland_ZL,
      extraMRNParams: extraMRNParams,
      poiId: poiId,
      spuId: spuId,
      shopUuid: shopUuid,
      poiCityID: poiCityID,
      channelCityID: channelCityID,
      conId: conId,
      isOfflineVIP: isOfflineVIP,
      checkinDate: checkinDate,
      checkoutDate: checkoutDate,
      checkin: checkin,
      checkout: checkout,
      roomNum: roomNum,
      adultNum: adultNum,
      childNum: childNum,
      childAge: childAge,
      isReschedule: isReschedule,
      oldOrderId: oldOrderId,
      propagate: propagate,
      isQuickExtension: isQuickExtension,
      roomNo: roomNo,
      retainWithBlindBoxDiscount: retainWithBlindBoxDiscount,
      coreSearchNoFixedAd: coreSearchNoFixedAd,
      ctPoi: ctPoi,
      queryId: queryId,
      applyId: applyId,
      isReceiveRedPacketSucceed: isReceiveRedPacketSucceed,
      continueLiveOrderId: continueLiveOrderId,
      superDealSceneType: superDealSceneType,
      superDealApplyId: superDealApplyId,
      superDealReservationType: superDealReservationType,
      receiveRedPacket: receiveRedPacket,
      oh_cancel_typeForPreview: oh_cancel_typeForPreview,
      oh_propagateDataFromDetailForPreview: oh_propagateDataFromDetailForPreview,
      isLowestPrice: isLowestPrice,
      notSuperDeal: !superDealSceneType || superDealSceneType <= 0,
      Incentive_Label: Incentive_Label,
      Incentive_Label_text: Incentive_Label_text,
      have_price_lable: have_price_lable,
      price_lable_text: price_lable_text,
      poiChannelScene: poiChannelScene,
      fromOffline: fromOffline,
      underLineShopSell: underLineShopSell,
      originGoodsStatus: originGoodsStatus,
      specialChannel: specialChannel,
      offlineSource: offlineSource,
      blindBoxSource: blindBoxSource
    ]
  }}
  number('goodsID') {{
    // duo ignore-check-var

    def checked = PAYLOAD.roomUpgrade ? PAYLOAD.roomUpgrade.checked : NODE.RoomUpgrade?.props?.isChecked
    if (checked) {
      // 如果选择了房型升级，使用升级后的 goodsID
      return NODE.RoomUpgrade.props.recommendedGoodsId
    }
    return PAGE_QUERY.goods_id ?: PAGE_QUERY.goodsId
  }}
  bool('hasSelectedLimitCoupon') {{
    def hasSelectedLimitCoupon = DATA_SOURCE?.data?.promotionVO?.availableCouponVOList
        ?.findAll { it.selectStatus == true }
        ?.any { it.needLimitGuestNum == true }
        ?: false
    return hasSelectedLimitCoupon    
  }}
  bool('isTourAround') {{
    // 判断是周边游
    !!DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagHeader?.title
  }}
  bool('isHourRoom') {{
    // 1：全日房，2：钟点房
    DATA_SOURCE?.data?.goodsVO?.goodsType == 2
  }}
  bool('hasCashBack') {{
    def hasDiscount = DATA_SOURCE?.data?.promotionVO?.activityVOList
                        ?.findAll {it -> it.overlayType != 46 && it.overlayType != 48 && it.overlayType != 49 } // 酒票返现
                        ?.any { it -> it.activityType == 1 }

    def hasCoupopn = 
    DATA_SOURCE?.data?.promotionVO?.availableCouponVOList?.findAll { it -> it.selectStatus }?.any { it -> it.applyType == 3 }

    return hasDiscount || hasCoupopn
  }}
  object('promotionShow') {{
    // ======= 境内、境外
    def bizType = PAGE_QUERY.biz_type
      ? (int) DF.toNumber(PAGE_QUERY.biz_type)
      : (PAGE_QUERY.oh_room_price_total ? 2 : 1)
    def isOversea = bizType == 2
    def isInland = !isOversea
    def isInland_ZL = bizType == 3
    // ======= 营销卡片各模块展示条件
    // 展示会员头部
    def isShowMemberHeader = (DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel > 0
        && !!DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.titleShow?.titleImg)
    // 是否展示会员权益。后端控制 isOfflineVIP 时不展示。
    def isShowRights = !!DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.rightsInfoVOList
    // 是否展示境外多单返现
    def isShowOverseaCashBack = isOversea && !!DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO?.taskDiscountDescInfo && !!DATA_SOURCE?.data?.priceVO?.linkedAmountVO?.overseaHotelCashBackTotalAmount
    // 是否展示住就送
    def isShowStayGift = !!DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.displayInfo?.zjsDisPlayModel;
    // 是否展示离店送积分
    def memberPointsVO = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO;
    def isShowMemberPoints = !!memberPointsVO?.title && !!memberPointsVO?.titleDesc;
    // 展示入住后返
    def isShowCheckinBack = !!DATA_SOURCE.data?.promotionVO?.promotionTipVO?.cashBackShowTipVO?.promotionPrompt && !!DATA_SOURCE.data?.priceVO?.linkedAmountVO?.totalCashBackAmountExceptLinked
    // 国内连订返现
    def taskCardVOList = DATA_SOURCE.data?.promotionVO?.taskCardVOList ?: [];
    def hasValidTaskActiveInfo = taskCardVOList.any { item ->
      def taskActiveVOList = item.taskActiveVOList ?: []
      return taskActiveVOList.size() > 0
    }
    def isShowinlandCashBack = isInland && hasValidTaskActiveInfo;

    // 国内【新】连订任务返现
    def newLinkedTaskCardVOList = DATA_SOURCE.data?.promotionVO?.linkedBookingTaskVO?.taskCardVOList ?: [];
    def isShowInlandNewLinkedTask = isInland && newLinkedTaskCardVOList?.taskCardVOList?.size() > 0;
        
    //是否展示可享优惠
    def isShowDiscountCard = !DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superGroupGoods;

    // 营销卡片是否只展示本单优惠。如果只有本单优惠，则标题不同。
    def isOnlyShowPromotion =
      isShowDiscountCard && 
      !isShowMemberHeader && 
      !isShowRights && 
      !isShowStayGift && 
      !isShowMemberPoints && 
      !isShowOverseaCashBack && 
      !isShowCheckinBack && 
      !isShowinlandCashBack &&
      !isShowInlandNewLinkedTask;
    // 展示普通头部标题。如果这个模块只展示本单优惠，则标题在本当优惠内
    def isShowNormalHeader = !isShowMemberHeader && !isOnlyShowPromotion;

    def isShow = isShowRights || isShowStayGift || isShowMemberPoints || isShowOverseaCashBack || isShowCheckinBack || isShowinlandCashBack || isShowDiscountCard;

    return [
      isShowRights: isShowRights,
      isShowStayGift: isShowStayGift,
      isShowMemberPoints: isShowMemberPoints,
      isShowOverseaCashBack: isShowOverseaCashBack,
      isShowCheckinBack: isShowCheckinBack,
      isShowinlandCashBack: isShowinlandCashBack,
      isShowInlandNewLinkedTask: isShowInlandNewLinkedTask, // 是否存在新连订任务
      isShowDiscountCard: isShowDiscountCard,

      isShow: isShow,
      isOnlyShowPromotion: isOnlyShowPromotion,
      isShowMemberHeader: isShowMemberHeader,
      isShowNormalHeader: isShowNormalHeader,
    ]
  }}
  object('defaultBookTimePeriod') {{
    // 钟点房入住时段列表
    def checkInPeriodList = DATA_SOURCE?.data?.goodsVO?.hourRoomVO?.checkInPeriodList;

    // 默认钟点房入住时段
    def defaultBookTimePeriod = checkInPeriodList?.size() > 0 
        ? (checkInPeriodList.find { !it.checkInNow } ?: checkInPeriodList[0]) 
        : null 

    return defaultBookTimePeriod;
  }}
  bool('isRoomUpgrade') {{
    // duo ignore-check-var

    PAYLOAD.roomUpgrade ? PAYLOAD.roomUpgrade.checked : NODE.RoomUpgrade?.props?.isChecked
  }}
  bool('registerFlagshipGroupMember') {{
    // duo ignore-check-var

    COMMON_PARAMS.isPreview || NODE.RegisterFlagshipMember?.props?.switchValue
  }}
  array('defaultSelectedRightsCode') {{
    DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.rightsInfoVOList?.findAll({ it.selectedStatus })?.collect({ it.rightsCode }) ?: []
  }}
  array('selectedSuperCouponList') {{
    // 选择的超团券列表
    return DATA_SOURCE?.data?.promotionVO?.availableCouponVOList
        ?.findAll { it.selectStatus == true && it.superGroupCoupon == true }
        ?: []
  }}
  bool('isSuperGroupScene') {{
    // 超团场景
    def spuExchangeType = DATA_SOURCE.data?.goodsVO?.spuInfoVO?.spuExchangeType;
    return spuExchangeType == 0 || spuExchangeType == 1 || spuExchangeType == 2 || spuExchangeType == 3;
  }}
  number('keyboardVerticalOffset') {{ COMMON_PARAMS.systemInfo?.platform == 'ios' ? 90 : -230 }}
  string('resSpuId') {{ DATA_SOURCE?.data?.goodsVO?.spuInfoVO?.spuId }}
  object('selectedLinkedTaskFromCache') {{
    if(COMMON_PARAMS?.systemInfo?.IS_DP || !COMMON_PARAMS?.userInfo?.userId || !COMMON_PARAMS.systemInfo?.isMRN) return [ selectedLinkedTasks: [], isValid: false ]

    def userId = COMMON_PARAMS?.userInfo?.userId
    def cacheObj = (COMMON_PARAMS.storage?.selectedLinkedTask instanceof String) && userId ? DF.jsonParse(COMMON_PARAMS.storage?.selectedLinkedTask ?: '{}') : null

    // 如果缓存不存在或为空，返回false（使用默认值）
    if (!cacheObj) {
        return [ selectedLinkedTasks: [], isValid: false ]
    }

    def cacheData = cacheObj?.get(userId)

    def selectedLinkedTasks = cacheData?.selectedMutiOrderTasks
    def expireCacheStamps = cacheData?.expireCacheStamps

    // 如果缓存不存在或为空，返回false（使用默认值）
    if (!selectedLinkedTasks || selectedLinkedTasks.size() == 0 || !expireCacheStamps) {
        return [ selectedLinkedTasks: [], isValid: false ]
    }

    // 检查时间戳是否存在
    if (expireCacheStamps) {
        def currentTimeStamp = System.currentTimeMillis()
        def cacheTimeStamp = expireCacheStamps ? (expireCacheStamps as Long) : 0L

        // 计算时间差（小时）
        def timeDiffHours = (currentTimeStamp - cacheTimeStamp) / (1000 * 60 * 60)
        // def timeDiffHours = currentTimeStamp - cacheTimeStamp

        // 如果缓存超过72小时，返回false（缓存过期，不使用缓存）
        if (timeDiffHours > 72) {
        // if (timeDiffHours > 60 * 1000) {
            return [ selectedLinkedTasks: [], isValid: false ]
        }
    }

    // 缓存存在且未过期，返回true（使用缓存）
    return [ selectedLinkedTasks: selectedLinkedTasks, isValid: true ]
  }}
  bool('isError') {{
    // 有中断弹窗时没有任何业务数据，按错误处理。
    if (DATA_SOURCE.data?.promptModuleVO?.orderBeforeExceptionPromptInfoVO) {
      return true
    }
    DATA_SOURCE.data == null || DATA_SOURCE.error != null
  }}
}
