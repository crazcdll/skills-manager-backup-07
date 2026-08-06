dataSource {
  dataSourceId '48'

  requestProps {
    objectWithSub('bookInfoParam') {
      number('goodsId') {{ CONST.goodsID }}
      number('checkinTime') {{
        if (COMMON_PARAMS.isSubmit || COMMON_PARAMS.isCheck) {
          def checkInPeriod = NODE.BookTime?.props?.checkInPeriod ?: NODE.SuperDealBookTime?.props?.checkInPeriod
          if (checkInPeriod?.checkinTime || PREV_DATA?.checkInTime){
            return checkInPeriod?.checkinTime ?: PREV_DATA.checkInTime;
          }
        }
        CONST.baseInfo.checkin + 'T00:00:00'
      }}
      number('checkoutTime') {{
        if (COMMON_PARAMS.isSubmit || COMMON_PARAMS.isCheck) {
          def checkInPeriod = NODE.BookTime?.props?.checkInPeriod ?: NODE.SuperDealBookTime?.props?.checkInPeriod
          if (checkInPeriod?.checkoutTime || PREV_DATA?.checkOutTime){
            return checkInPeriod?.checkoutTime ?: PREV_DATA.checkOutTime;
          }
        }
        CONST.baseInfo.checkout + 'T00:00:00'
      }}
      number('roomNum') {{
        // preview
        if (COMMON_PARAMS.isPreview) {
          return CONST.baseInfo.roomNum
        }
        PAYLOAD?.roomNum?.value ?: PREV_DATA.roomCount
      }}
      number('adultNum') {{ CONST.baseInfo.adultNum }}
      array('childrenAgeList') {{ CONST.baseInfo.childAge }}
      number('arriveTime') {{
        if (!COMMON_PARAMS.isSubmit) return null
        NODE.GuestCard?.props?.arriveTimeObj?.arriveTime
      }}
      number('guestType') {{
        if (!COMMON_PARAMS.isSubmit && !COMMON_PARAMS.isCheck) return null
        return PREV_DATA.guestType
      }}
      string('email') {{
        if (!COMMON_PARAMS.isSubmit) return null
        if (NODE.GuestCard?.props?.countryCode?.Key == '86' && !CONST.baseInfo.isOversea) return null
        NODE.GuestCard?.props?.email
      }}
      array('specialRequestIdList') {{
        if ( NODE.PreferenceInfo?.props?.preferenceSelectInfo?.specialRequestIds) {
          def specialRequestIds = NODE.PreferenceInfo?.props?.preferenceSelectInfo?.specialRequestIds?.split(',') ?: []
          // 只取非空的
          return specialRequestIds?.findAll({ it })
        }
        return []
      }}
      string('specialRequestAdditionalNote') {{ NODE.PreferenceInfo?.props?.preferenceSelectInfo?.additional }}
      number('userId') {{ COMMON_PARAMS.userInfo.userId }}
      string('token') {{ COMMON_PARAMS.userInfo.token }}
      array('guestInfoTable') {{
        // 旗舰店校验时入参也传 guestInfoTable
        if (!COMMON_PARAMS.isSubmit && PAYLOAD.validateType != 2) return null

        def guestInfo = NODE.GuestCard?.props?.guestInfo

        def guestInfoTable = guestInfo?.collect { room ->
            room.guestList?.collect { guest ->
                def englishName = guest.lastName + "/" + guest.firstName
                def name = PREV_DATA.guestType == 1 ? (guest.chineseName ?: englishName) : englishName
                return [
                    identityType: guest.identityType,
                    identity: guest.identity,
                    name: name
                ]
            }
        }

        if (PREV_DATA?.isTourAround) {
            def roomNum = (int) DF.toNumber(PREV_DATA.roomCount ?: CONST.baseInfo.roomNum)
            def length = roomNum > guestInfoTable?.size() ? guestInfoTable?.size() : roomNum
            return guestInfoTable?.subList(0, length)
        }

        return guestInfoTable
      }}
      string('countryCallingCode') {{
        if (!COMMON_PARAMS.isSubmit) return null
        NODE.GuestCard?.props?.countryCode?.Key
      }}
      string('contactorPhone') {{
        if (!COMMON_PARAMS.isSubmit && !COMMON_PARAMS.isCheck) return null
        NODE.GuestCard?.props?.phoneNum
      }}
      string('roomNumber') {{
        // 店内服务房间号
        if (!COMMON_PARAMS.isSubmit) return null
        NODE.GuestCard?.props?.roomNo
      }}
      number('poiId') {{ PREV_DATA?.poiId ?: CONST.baseInfo.poiId }}
      number('partnerId') {{
        if (COMMON_PARAMS.isPreview) {
          return PAGE_QUERY.partnerId
        }
        return PREV_DATA.partnerId
      }}
      number('childNum') {{ CONST.baseInfo.childNum }}
      string('specialRequestAdditionalNoteCodes') {{ NODE.PreferenceInfo?.props?.preferenceSelectInfo?.noteItemSelected?.join(',') }}
      bool('checkInNow') {{
        NODE.BookTime?.props?.checkInPeriod?.checkinNow ?: NODE.SuperDealBookTime?.props?.checkInPeriod?.checkinNow
      }}
      number('spuId') {{
        // 优先page_query.spuId，兜底page_query.spuid
        CONST.baseInfo.spuId
      }}
      string('ticketCheckInTime') {{
        // preview返回null
        if (COMMON_PARAMS.isPreview) return null;
        // submit和update请求,ticketCheckInTime的值存在
        def ticketCheckInTime = PAYLOAD.ticketCheckInTime ?: NODE?.UniversalCalendar?.props?.ticketCheckInTime
        if (!!ticketCheckInTime) {
          def year = ticketCheckInTime.substring(0, 4);
          def month = ticketCheckInTime.substring(4, 6);
          def day = ticketCheckInTime.substring(6, 8);
          return year + "-" + month + "-" + day + "T00:00:00";
        }
        return null;
      }}
      array('giftBagTouristTable') {{
        if (!COMMON_PARAMS.isSubmit ) return null

        if(!PREV_DATA?.isTourAround) return null

        def guestInfo = NODE.GuestCard?.props?.guestInfo

        def guestInfoTable = guestInfo?.collect { room ->
            room.guestList?.collect { guest ->
                def englishName = guest.lastName + "/" + guest.firstName
                def name = PREV_DATA.guestType == 1 ? (guest.chineseName ?: englishName) : englishName
                return [
                    identityType: guest.identityType,
                    identity: guest.identity,
                    name: name
                ]
            }
        }

        def needIdentityNums = (int) DF.toNumber(PREV_DATA?.needIdentityNums) ?: 0

        if(needIdentityNums <= 0 || needIdentityNums > guestInfoTable?.size()) return null

        return guestInfoTable?.subList(0, needIdentityNums)?.collect { room -> [room.getAt(0)] }
      }}
    }
    objectWithSub('promotionParam') {
      number('groupMemberDiscountAmount') {{
        if (PAYLOAD.validateType != 2) {
          // validateType 表示旗舰店校验时机。
          return null
        }
        // 透传主接口返回的
        PREV_DATA.flagship?.groupMemberDiscountAmount
      }}
      bool('selectedRefreshPromotion') {{
        if(COMMON_PARAMS.isSubmit) return true
        if(PREV_DATA?.isSuperGroupBuy && (COMMON_PARAMS?.isPreview || COMMON_PARAMS?.isUpdate)) return false
        if (PAYLOAD.refreshPromotion) return false
        COMMON_PARAMS.isUpdate
      }}
      string('superDealApplyId') {{ CONST.baseInfo?.superDealApplyId }}
      number('linkedBookingCheckType') {{
        // 小程序先屏蔽连订能力
        if (!COMMON_PARAMS.systemInfo?.isMRN) return null;
        if (CONST.baseInfo.isInland) return null;
        // 2表示有代扣活动未勾选 3表示有代扣活动用户勾选 4表示有返现活动
        def ACTION_DEFAULT = 1;
        def UNSELECTED = 2;
        def SELECTED = 3;
        def CASH_BACK = 4;
        // 联订返现类型
        def ACTION_CASH_BACK = 100010;
        // 返现活动第二单
        def SECOND_ORDER = 2;

        // 境外preview
        if (COMMON_PARAMS.isPreview) {
          def linkedBookingCheckType = CONST.baseInfo.extraMRNParams?.linkedBookingCheckType;
          // 超团场景屏蔽联订活动
          if (CONST.baseInfo.superDealSceneType) {
            return ACTION_DEFAULT;
          }
          // 返现活动
          if (linkedBookingCheckType == CASH_BACK) {
            return CASH_BACK;
          }
          return linkedBookingCheckType ?: UNSELECTED;
        }
        // 境外 update submit
        if (CONST.baseInfo.superDealSceneType) {
          return ACTION_DEFAULT;
        }
        // 联订返现 第二单传2
        if (PREV_DATA.linkedBookingInfo?.actionType == ACTION_CASH_BACK && PREV_DATA.linkedBookingInfo?.taskOrderStatus == SECOND_ORDER) {
          return UNSELECTED;
        }
        // 联订返现 第一单传4
        if (PREV_DATA.linkedBookingInfo?.actionType == ACTION_CASH_BACK) {
          return CASH_BACK;
        }
        def isChecked = PAYLOAD?.multipleBookingTask ? PAYLOAD.multipleBookingTask?.checked : NODE?.OverseaMultipleTask?.props?.isSelectedTaskCard;
        return isChecked ? SELECTED : UNSELECTED;
      }}
      array('selectedPromotionList') {{
        if (PAYLOAD.refreshPromotion) return null
        if (PREV_DATA?.isSuperGroupBuy && (COMMON_PARAMS?.isPreview || COMMON_PARAMS?.isUpdate)) return null

        def selectedCommonCoupons = PAYLOAD.selectedCommonCoupons
        if(selectedCommonCoupons == null) {
          def filteredCommonCoupons = PREV_DATA.selectedCommonCoupons ?: []
          // 剔除实名券
          if(NODE.LifecycleLogic?.props?.removeRealNameVoucher) {
            filteredCommonCoupons = filteredCommonCoupons?.findAll {it -> !it.realNameCheck}
          }

          // 剔除风控券
          def failMagicCards = NODE.LifecycleLogic?.props?.failPromotion?.failMagicCards
          if(failMagicCards) {
            filteredCommonCoupons = filteredCommonCoupons?.findAll {it -> !failMagicCards?.contains(it?.id)}
          }

          selectedCommonCoupons = filteredCommonCoupons?.collect {it -> [id: it.id, promotionSource: it.promotionSource]}
        }


        // 剔除风控活动
        def failActiveIdList = NODE.LifecycleLogic?.props?.failPromotion?.failActiveIdList
        def filteredActivityParams = failActiveIdList ?
          PREV_DATA.selectedActivityParams?.findAll {it -> !failActiveIdList?.contains(it?.id)} :
          PREV_DATA.selectedActivityParams

        def magicalCouponParams = PAYLOAD.selectedMagicalCoupons != null ? PAYLOAD.selectedMagicalCoupons : PREV_DATA.selectedMagicalCoupons

        return (filteredActivityParams ?: []) + (selectedCommonCoupons ?: []) + (magicalCouponParams ?: [])
      }}
      array('queryMasterCouponIds') {{ PAYLOAD?.eachInflateParams?.queryMasterCouponIds }}
      bool('useSuperDealCoupon') {{
        // 主流程不使用超团券，固定传false
        if(CONST.baseInfo?.notSuperDeal && NODE.PromotionDiscountCard?.props?.noUseSuperDealCoupon == true) return false
      }}
      string('superDealCouponCode') {{
        if (CONST.baseInfo.isOversea) return null
        if (PAGE_QUERY?.giftCardCode) {
         return PAGE_QUERY?.giftCardCode
        }

        if(COMMON_PARAMS.isSubmit){
          def redPacket = PREV_DATA.selectedCommonCoupons? PREV_DATA.selectedCommonCoupons[0] : null
          if (redPacket && redPacket?.superGroupCoupon && redPacket?.id){
            return redPacket.id
          }
        }
      }}
      bool('receiveRedPacket') {{
        if(COMMON_PARAMS.isSubmit) return null
        CONST.baseInfo.receiveRedPacket
      }}
      array('linkedBookingCheckList') {{
        if (!COMMON_PARAMS.systemInfo?.isMRN) return null;
        if (CONST.baseInfo.isOversea) return [];

        if (COMMON_PARAMS.isPreview) {
          def selectedLinkedTasks = CONST.selectedLinkedTaskFromCache?.selectedLinkedTasks
          return (selectedLinkedTasks?.size() > 0) ? selectedLinkedTasks : null
        }
        return PAYLOAD?.inlandMultipleBookingTask?.linkedCheckList ?: NODE?.InlandMultipleTask?.props?.linkedCheckList ?: []
      }}
      array('couponBackIdList') {{
        if(PREV_DATA?.couponBackList?.size() > 0) {
          return PREV_DATA?.couponBackList?.
                  collect { it -> it.activeIds }?.
                  collectMany { it }?.
                  findAll { it }
        }
      }}
      bool('linkedBookingUseCheckTypeDefault') {{
        if (!COMMON_PARAMS.systemInfo?.isMRN) return null;
        // 若客户端不存在连订任务缓存时，告知后端使用增长下发的连订任务默认值
        def isUseDefaultLinkedTask = !CONST.selectedLinkedTaskFromCache?.isValid
        return isUseDefaultLinkedTask
      }}
    }
    objectWithSub('memberParam') {
      bool('canUseMemberDiscountPriceBook') {{
        if (!COMMON_PARAMS.isSubmit) {
          // 只有 submit 需要，其他生命周期 true
          return true
        }
        if (!COMMON_PARAMS.systemInfo?.isMRN) {
          // 非MRN兜底true
          return true
        }
        def flagship = PREV_DATA.flagship
        // 如果不是旗舰店: 写死 true。比如雅朵不是旗舰店，但是可以使用会员价。
        if (!flagship?.groupFlagShipGoods) {
          return true
        }
        // 校验接口返回弹窗后，选择“原价下单”，此时会再次执行校验。下单时应写死 false。
        if (PAYLOAD.flagshipNoDiscount) {
          return false
        }
        // 如果是会员（以前注册过）: 用校验接口返回的“是否可以使用会员价”。
        if (flagship?.groupFlagShipMember) {
          // 如果没有执行校验，则用 false
          return PAYLOAD.flagshipValidateResult?.canUseMemberDiscountPriceBook ?: false
        }
        // 如果本次注册会员: 写死 true; 本次不注册: 写死 false。
        return !!NODE.RegisterFlagshipMember?.props?.switchValue
      }}
      number('groupMemberLevel') {{
        if (PAYLOAD.validateType != 2) {
          // validateType 表示旗舰店校验时机。
          return null
        }
        // 透传主接口返回的; 如果是本次注册，主接口不返回，为空。
        PREV_DATA.flagship?.groupMemberLevel
      }}
      string('groupMemberName') {{
        if (PAYLOAD.validateType != 2) {
          // validateType 表示旗舰店校验时机。
          return null
        }
        // 透传主接口返回的; 如果是本次注册，主接口不返回，为空。
        PREV_DATA.flagship?.groupMemberName
      }}
      array('groupMemberIdentities') {{
        if (PAYLOAD.validateType != 2) {
          // validateType 表示旗舰店校验时机。
          return null
        }
        NODE.GuestCard?.props?.guestInfo
          .collectMany({ it.guestList }) // 打平二维数组
          .collect({ it.identity }) // 获取身份证号
          .findAll({ it != null }) // 只取非空的
      }}
      bool('supportMemberSubscribe') {{
        if (PAYLOAD.validateType != 2) {
          // validateType 表示旗舰店校验时机。
          return null
        }
        // 透传主接口返回的
        PREV_DATA.flagship?.supportMemberSubscribe
      }}
      bool('registerFlagshipGroupMember') {{ CONST.registerFlagshipGroupMember }}
      number('pointsNum') {{
        PAYLOAD.pointsNum != null ?
          (PAYLOAD.pointsNum == 0 ?
            null :
            PAYLOAD.pointsNum
          ) :
          PREV_DATA.selectedPoint
      }}
      bool('useCustomPointsNum') {{
        PAYLOAD?.useCustomPointsNum != null ? PAYLOAD?.useCustomPointsNum : PREV_DATA.useCustomPointsNum
      }}
      array('selectedRightsInfo') {{
        if (!COMMON_PARAMS.isSubmit && !COMMON_PARAMS.isPreview) {
          return null
        }
        def res = []
        // 拼上折扣
        if (PREV_DATA.discountRights) {
          res += [PREV_DATA.discountRights]
        }
        // 拼上会员权益
        def rightsList = NODE.Rights?.props?.value?.selected?.findAll({ it.selectedStatus })
        if (rightsList) {
          res += rightsList
        }
        // 拼上住就送
        if (PREV_DATA.zjsRights) {
          res += [PREV_DATA.zjsRights]
        }
        res
      }}
      bool('signup4Flagship') {{ NODE?.MarriottMemberCard?.props?.signUpFlagship }}
      object('pointsPromotionInfo') {{
        if (!COMMON_PARAMS.isSubmit) {
          return null
        }
        return PREV_DATA.jfqedRights
      }}
      object('returnPointsParam') {{
        if (!COMMON_PARAMS.isSubmit) return null

        return PREV_DATA?.returnPointsParam
      }}
      string('memberIdentity') {{
        // 小程序没有旗舰店功能，先屏蔽
        if (!COMMON_PARAMS.systemInfo?.isMRN) return null

        def flagShipVIPGoods = PREV_DATA?.flagship?.groupFlagShipGoods

        if(flagShipVIPGoods) {
          def registerMember = NODE.RegisterFlagshipMember?.props?.switchValue
          def groupFlagShipMember = PREV_DATA?.flagship?.groupFlagShipMember

          if (groupFlagShipMember && PAYLOAD.flagshipValidateResult?.canUseMemberDiscountPriceBook){
            def guestInfo = NODE.GuestCard?.props?.guestInfo
            return guestInfo?.getAt(0)?.guestList?.getAt(0)?.identity
          } else if (!groupFlagShipMember && registerMember)
            return NODE?.RegisterFlagshipMember?.props?.memberIdentity
        }
      }}
      bool('needMemberAuthenticated') {{
        def needMemberAuthenticated = NODE?.RegisterFlagshipMember?.props?.needMemberAuthenticated
        return needMemberAuthenticated != null ? needMemberAuthenticated : true
      }}
    }
    objectWithSub('couponPackageParam') {
      string('position') {{
        def fromPromotion = NODE.PromotionDiscountCard?.props?.useVoucherPosition
        def isOversea = CONST.baseInfo.isOversea
        if (COMMON_PARAMS.systemInfo?.envInWeb?.isWebInWeChatMiniProgram) {
          if (isOversea) return null
          return !fromPromotion ? '1109' : '1110'
        }
        def IS_DP = COMMON_PARAMS?.systemInfo?.IS_DP
        def danDanPengPosition = IS_DP ? '3140' : '2140'
        def firstInflatePosition = !fromPromotion ?
          IS_DP && !isOversea ? '3109' : '2109' :
          IS_DP && !isOversea ? '3110' : '2110'
        return isOversea || COMMON_PARAMS.isSubmit ? firstInflatePosition : firstInflatePosition + ',' + danDanPengPosition
      }}
      string('mmcPreToken') {{
        if (PAYLOAD.refreshMagicalCouponPackage) return null

        if (COMMON_PARAMS.isSubmit) {
          return PREV_DATA.selectedMagicalCouponPackage?.mmcPreToken
        }

        if (PAYLOAD.magicalCouponPackageParams?.mmcPreToken != null){
          return PAYLOAD.magicalCouponPackageParams?.mmcPreToken
        }

        if (PREV_DATA.selectedMagicalCouponPackage?.mmcPreToken) {
          return PREV_DATA.selectedMagicalCouponPackage?.mmcPreToken
        }

        return null
      }}
      bool('mmcPreGrant') {{
        if (PAYLOAD.refreshMagicalCouponPackage) return null
        if(!COMMON_PARAMS.isUpdate) return null
        if(PAYLOAD.magicalCouponPackageParams?.mmcPreGrant != null) return PAYLOAD.magicalCouponPackageParams?.mmcPreGrant
      }}
      bool('mmcPreInflate') {{
        if (PAYLOAD.refreshMagicalCouponPackage) return null
        if(!COMMON_PARAMS.isUpdate) return null
        if(PAYLOAD.magicalCouponPackageParams?.mmcPreInflate != null) return PAYLOAD.magicalCouponPackageParams?.mmcPreInflate
      }}
      string('mmcBaseCouponInfo') {{
        if (PAYLOAD.refreshMagicalCouponPackage) return null
        PAYLOAD.magicalCouponPackageParams?.mmcBaseCouponInfo?.isEmpty() ?
          null :
          PAYLOAD.magicalCouponPackageParams?.mmcBaseCouponInfo ?: PREV_DATA.selectedMagicalCouponPackage?.baseCouponInfo
      }}
      string('bizToken') {{
        if (PAYLOAD.refreshMagicalCouponPackage) return null
        PAYLOAD.magicalCouponPackageParams?.bizToken?.isEmpty() ?
          null :
          PAYLOAD.magicalCouponPackageParams?.bizToken ?: PREV_DATA.selectedMagicalCouponPackage?.bizToken
      }}
      string('selectedCouponPackageId') {{
        if (PAYLOAD.refreshMagicalCouponPackage) return null
        if (!COMMON_PARAMS.isUpdate) return null
        PAYLOAD.magicalCouponPackageParams?.selectedCouponPackageId?.isEmpty() ?
          null :
          PAYLOAD.magicalCouponPackageParams?.selectedCouponPackageId ?: PREV_DATA.selectedMagicalCouponPackage?.couponPackageId
      }}
      string('mmSkuParamStr') {{
        if (!COMMON_PARAMS.isSubmit) return null
        PREV_DATA.selectedMagicalCouponPackage?.skuParamStr
      }}
      bool('needSelectMagicalMemberCoupon') {{ NODE.PromotionDiscountCard?.props?.needSelectMagicalMemberCoupon ?: false }}
    }
    objectWithSub('groupBuyProductParam') {
      string('mboxId') {{
        if (COMMON_PARAMS.isSubmit) {
          return PREV_DATA.mboxId
        }
        return null
      }}
      string('preGrantId') {{
        if (COMMON_PARAMS.isSubmit) {
          return PREV_DATA.preGrantId
        }
        return null
      }}
      number('payAmount') {{
        if (COMMON_PARAMS.isSubmit) {
          return PREV_DATA.groupBuyProductPayMoney
        }
        return null
      }}
      array('groupBuyCouponParamList') {{
        if (COMMON_PARAMS.isSubmit) {
          return PREV_DATA.groupBuyCouponList
        }
        return null
      }}
    }
    object('insuranceParam') {{
      // preview请求
      if (COMMON_PARAMS.isPreview) {
        return null
      }
      // PALOAD.insuranceTying信息存在
      if (PAYLOAD?.insuranceTying) {
        return [
          accidentPackageId: PAYLOAD.insuranceTying?.accidentPackageId,
          accidentInsurancePremium: PAYLOAD.insuranceTying?.accidentInsurancePremium,
          accidentInsuredPersonList: PAYLOAD.insuranceTying?.accidentInsuredPersonList ?: [],
        ]
      }
      // 选中保险项
      def selectedInsurance = PREV_DATA.selectedInsurance
      if (selectedInsurance) {
        // 被保人信息
        def insuredPerson = NODE.InsuranceTying?.props?.allInsuredPersonList ?: [:]
        // 选中项被保人
        def selectedInsurancePerson = insuredPerson[selectedInsurance?.packageId?.toString()]
        // 格式化选中项被保人
        def formatInsurancePerson = selectedInsurancePerson?.collect { item ->
          [
            // 写死身份证
            identityType: 1,
            identity: item.identity,
            name: item.chineseName,
          ]
        } ?: []
        return [
          accidentPackageId: selectedInsurance?.packageId,
          accidentInsurancePremium: selectedInsurance?.premium,
          accidentInsuredPersonList: formatInsurancePerson ?:[]
        ]
      }
      return null
    }}
    objectWithSub('payParam') {
      bool('supportMonthPayPreAuth') {{
        if (!COMMON_PARAMS.systemInfo?.isMRN) return null
        if (!COMMON_PARAMS.isSubmit) {
          return null
        }
        return PREV_DATA?.supportMonthPayPreAuth && !PREV_DATA?.selectedInsurance
      }}
      string('cashierTypeStr') {{
        if (!COMMON_PARAMS.systemInfo?.isMRN) return null
        if (!COMMON_PARAMS.isSubmit) {
          return null
        }
        return NODE.HfeHotelSubmitPrePay?.props?.prePayInfo?.launchPaymentCashierParams?.cashier_type
      }}
      string('payExtraData') {{
        if (!COMMON_PARAMS.systemInfo?.isMRN) return null
        if (!COMMON_PARAMS.isSubmit) {
          return null
        }

        def data = NODE.HfeHotelSubmitPrePay?.props?.prePayInfo?.launchPaymentCashierParamsExtraData

        return DF.toJsonString(data)
      }}
      number('roomFeeAmount') {{
        def roomMoney = PREV_DATA.roomFeeAmount ?: 0

        if(PREV_DATA.payType == 2) {
          roomMoney = PREV_DATA?.cashRoomFeeAmount ?: 0
        }

        def flagship = PREV_DATA.flagship
        def bookingForOthersWithoutVIPPrice = flagship?.groupFlagShipMember && PAYLOAD.flagshipValidateResult?.canUseMemberDiscountPriceBook == false
        def noRegister = !flagship?.groupFlagShipMember && !NODE.RegisterFlagshipMember?.props?.switchValue
        def needAddVipDiscount = bookingForOthersWithoutVIPPrice || noRegister

        if (flagship?.groupFlagShipGoods && needAddVipDiscount) {
          def vipDiscount = flagship?.groupMemberDiscountAmount ?: 0
          roomMoney = roomMoney + vipDiscount
        }

        return roomMoney
      }}
      number('totalPayAmount') {{
        def payMoney = PREV_DATA.totalPayAmount ?: 0
        def flagship = PREV_DATA.flagship
        if (flagship?.groupFlagShipGoods && flagship?.groupFlagShipMember && PAYLOAD.flagshipValidateResult?.canUseMemberDiscountPriceBook == false ) {
          def vipDiscount = PREV_DATA.flagship?.groupMemberDiscountAmount ?: 0
          payMoney = payMoney + vipDiscount
        }
        return payMoney
      }}
      number('totalPromotionAmount') {{ PREV_DATA.totalPromotionAmount }}
      number('totalActivityAmount') {{ PREV_DATA.totalActivityAmount }}
      number('totalCouponAmount') {{ PREV_DATA.totalCouponAmount }}
      number('diffAmount') {{
        if(!CONST.baseInfo.isReschedule) return null
        PREV_DATA.diffAmount
      }}
    }
    objectWithSub('distributionParam') {
      array('attributionChannelInfoList') {{
        if(!PAGE_QUERY.adVisitPointFrom) return null
        [[
          attributionType: 'hoteldingdantong',
          sceneId: PAGE_QUERY.adVisitPointFrom
        ]]
      }}
      string('distributionLchId') {{
        if (COMMON_PARAMS.isSubmit) {
          return CONST.baseInfo?.extraMRNParams?.lch ?: PAGE_QUERY?.distributionLchId
        }
      }}
      string('distributionUnpl') {{
        if(!COMMON_PARAMS.isSubmit || COMMON_PARAMS?.systemInfo?.IS_DP || CONST.baseInfo?.isOversea) return null
        COMMON_PARAMS.storage.distributionUnpl ?: PAGE_QUERY?.distributionUnpl ?: ''
      }}
    }
    objectWithSub('environmentParam') {
      number('platform') {{
        if (COMMON_PARAMS.systemInfo.IS_DP) {
          return 2
        }
        if (COMMON_PARAMS.systemInfo.IS_MT) {
          return 1
        }
        return 1
      }}
      string('version') {{ COMMON_PARAMS.systemInfo.version }}
      string('osVersion') {{ COMMON_PARAMS.systemInfo.systemVersion }}
      string('uuid') {{
        if(COMMON_PARAMS.systemInfo?.isMRN) return COMMON_PARAMS.userInfo.mtuuid
        COMMON_PARAMS.userInfo.uuid
      }}
      string('dpid') {{ COMMON_PARAMS.userInfo.dpid }}
      string('userAgent') {{ SYSTEM_INFO['user-agent'] }}
      bool('mrn') {{ COMMON_PARAMS.systemInfo.isMRN }}
      objectWithSub('miniProgramParam') {
        string('appType') {{ 'WEIXINPROGRAM' }}
        string('programName') {{
          if (COMMON_PARAMS.systemInfo.envInWeb.isWebInWeChatMiniProgram) {
            if (COMMON_PARAMS.systemInfo.IS_HOTEL) {
              return 'hotel'
            }
            if (COMMON_PARAMS.systemInfo.IS_DP) {
              return 'dp'
            }
            if (COMMON_PARAMS.systemInfo.IS_MT) {
              return 'mt'
            }
          }
        }}
        string('appId') {{ COMMON_PARAMS.systemInfo.mpAppId }}
        string('openId') {{ COMMON_PARAMS.userInfo.openId }}
        string('version') {{ COMMON_PARAMS.systemInfo.mpAppVersion }}
        string('appletsFingerprint') {{ PAGE_QUERY?.appletsFingerprint }}
        objectWithSub('weChatClientParam') {
          string('wechatRiskParams') {{
            // 酒店特有小程序风控参数
            PAGE_QUERY?.wechatRiskParams
          }}
        }
      }
      objectWithSub('geoParam') {
        string('longitude') {{ COMMON_PARAMS.location.lng }}
        string('latitude') {{ COMMON_PARAMS.location.lat }}
        number('pageCityId') {{ COMMON_PARAMS.cityInfo.cityId }}
        number('userCityId') {{ COMMON_PARAMS.cityInfo.locCityId }}
        number('poiCityId') {{ CONST.baseInfo.poiCityID }}
        number('channelCityId') {{ CONST.baseInfo.channelCityID }}
        bool('hotelCustomGpsStatus') {{
          if(PAYLOAD?.hotelCustomGpsStatus != null ) {
            return PAYLOAD.hotelCustomGpsStatus
          }
          !!COMMON_PARAMS.location.lat && !!COMMON_PARAMS.location.lng
        }}
      }
      objectWithSub('riskParam') {
        string('fingerprint') {{ COMMON_PARAMS?.fingerprint.fingerprint }}
      }
      objectWithSub('utmParam') {
        string('utmContent') {{
          if(CONST.baseInfo?.fromOffline && CONST.baseInfo?.underLineShopSell) {
            def res = [source: 'WXXXGY']
            def originGoodsStatus = CONST.baseInfo?.originGoodsStatus
            if (originGoodsStatus || originGoodsStatus == 0) {
              res = [source: 'WXXXGY', originGoodsStatus: originGoodsStatus]
            }
            return DF.toJsonString(res)
          }
          SYSTEM_INFO.utm_content ?: PAGE_QUERY?.utmContent
        }}
        string('utmSource') {{ SYSTEM_INFO.utm_source ?: PAGE_QUERY?.utmSource }}
        string('utmMedium') {{ SYSTEM_INFO.utm_medium ?: PAGE_QUERY?.utmMedium }}
        string('utmTerm') {{ SYSTEM_INFO.utm_term ?: PAGE_QUERY?.utmTerm }}
        string('utmCampaign') {{ SYSTEM_INFO.utm_campaign ?: PAGE_QUERY?.utmCampaign }}
      }
      string('ip') {{ SYSTEM_INFO.realRemoteIp }}
    }
    objectWithSub('bizParam') {
      number('bizType') {{ CONST.baseInfo.bizType }}
      number('specialChannel') {{ CONST.baseInfo?.specialChannel ?: 0 }}
      bool('fromOffline') {{ CONST.baseInfo?.fromOffline }}
      number('offlineSource') {{ CONST.baseInfo?.offlineSource }}
      bool('offlineInventory') {{ CONST.baseInfo?.fromOffline && CONST.baseInfo?.underLineShopSell }}
      bool('coreSearchNoFixedAd') {{ CONST.baseInfo.coreSearchNoFixedAd }}
      number('superDealSceneType') {{ CONST.baseInfo?.superDealSceneType }}
      number('superDealReservationType') {{ CONST.baseInfo.superDealReservationType }}
      bool('retainWithBlindBoxDiscount') {{
        NODE.LifecycleLogic?.props?.retainWithBlindBoxDiscount ?: CONST.baseInfo.retainWithBlindBoxDiscount
      }}
      number('roomUpgradeType') {{
        // 房型升级时需要
        if (PAYLOAD.roomUpgrade) {
          return PAYLOAD.roomUpgrade.checked ? 1 : 2
        }
        // 非房型升级，0
        return null
      }}
      bool('roomUpgrade') {{ CONST.isRoomUpgrade }}
      string('blindBoxSource') {{
        def blindBoxSource = CONST.baseInfo?.blindBoxSource ?: ''
        // preview
        if (COMMON_PARAMS.isPreview) {
          return blindBoxSource;
        }
        // update submit check
        return NODE?.LifecycleLogic?.props?.blindBoxSource ?: blindBoxSource;
      }}
      bool('lowerCarbon') {{ NODE.LowerCarbon?.props?.isChecked ?: false }}
      bool('privacyOrder') {{ NODE.PrivacyProtection?.props?.privacyPolicyCheckStatus }}
      string('propagateData') {{
        // 境外propagate手动拼接 isPreview传递
        if (COMMON_PARAMS.isPreview && CONST.baseInfo.isOversea) {
          return DF.toJsonString([
            price: PAGE_QUERY?.oh_room_price_total,
            cancelRule: CONST.baseInfo.oh_cancel_typeForPreview,
            contentTransparent: CONST.baseInfo.oh_propagateDataFromDetailForPreview ?: '',
          ])
        }
        // 判断选择的券中存在超团商促券
        def noUsePromoSuperDeal = CONST.baseInfo?.notSuperDeal && NODE.PromotionDiscountCard?.props?.noUseSuperDealCoupon
        if (!CONST.baseInfo.isOversea && !CONST.isRoomUpgrade && !noUsePromoSuperDeal) {
          return CONST.baseInfo.propagate
        }
      }}
      number('continuousOrderUserType') {{
        // 连订用户所属业务类型 1:机票来源 2:火车票来源 3:门票来源
        CONST.baseInfo?.extraMRNParams?.continuousOrderUserType
      }}
      number('sourceChannelPage') {{ CONST.baseInfo.extraMRNParams?.isTourAround ? 1 : 0 }}
      string('specAttributionChannel') {{
        PAGE_QUERY?.specAttributionChannel ?: CONST.baseInfo.extraMRNParams?.specAttributionChannel ?: ''
      }}
      number('costSourceChannel') {{ CONST.baseInfo?.specialChannel ?: 0 }}
      bool('selfServiceCheckin') {{
        if(!COMMON_PARAMS.isSubmit) return null
        def roomNum = PREV_DATA.roomCount ?: CONST.baseInfo?.roomNum
        PREV_DATA?.identityNumType == 2 && roomNum > 1
      }}
      bool('lowestPriceInPoi') {{ CONST.baseInfo?.isLowestPrice }}
      number('poiChannelScene') {{ COMMON_PARAMS.isSubmit ? CONST.baseInfo?.poiChannelScene : null }}
    }
    objectWithSub('extendParam') {
      string('traceIdFromOrderBefore') {{ PREV_DATA.traceId }}
      string('extInfo') {{ PREV_DATA?.extInfo }}
      objectWithSub('validateParam') {
        bool('firstCreateOrderValidate') {{
          if (PAYLOAD.validateType != 2) {
            // validateType 表示旗舰店校验时机。
            return null
          }
          // 校验失败，弹窗选择原价下单：false
          if (PAYLOAD.flagshipNoDiscount) {
            return false
          }
          def flagship = PREV_DATA.flagship
          // 如果不是旗舰店，或已注册: true。
          if (!flagship?.groupFlagShipGoods || flagship?.groupFlagShipMember) {
            return true
          }
          return false
        }}
        array('validateOptions') {{
          if (COMMON_PARAMS.isCheck) {
            return PREV_DATA.createOrderNeedValidateCheckTypes
          }
        }}
        number('validateType') {{ PAYLOAD.validateType }}
        bool('repeatOrderValidate') {{
          if (!COMMON_PARAMS.isSubmit) {
            // 只有 submit 需要，其他生命周期 null
            return null
          }
          !PAYLOAD.skipRepeatOrderValidate
        }}
        bool('hourRoomCheckValidate') {{
          if (!COMMON_PARAMS.isSubmit) {
            // 只有 submit 需要，其他生命周期 null
            return null
          }
          !PAYLOAD.skipHourRoomValidate
        }}
        number('hourRoomTypeLimitValue') {{ PREV_DATA.typeLimitValue }}
        bool('cancelRuleChangeValidate') {{
          if (!COMMON_PARAMS.isSubmit) {
            // 只有 submit 需要，其他生命周期 null
            return null
          }
          !PAYLOAD.skipCancelRuleChangeValidate
        }}
        number('beforeCancelRuleMode') {{ PREV_DATA.beforeCancelRuleMode }}
      }
      bool('useSelectedActivities') {{ !!NODE.LifecycleLogic?.props?.failPromotion }}
      string('snapshot') {{ PREV_DATA?.snapshot }}
      string('conId') {{ CONST.baseInfo.conId }}
      objectWithSub('oldDiffParam') {
        string('preResponse') {{ PAYLOAD.oldDiffParam?.preResponse }}
        string('preTraceId') {{ PAYLOAD.oldDiffParam?.preTraceId }}
        string('bundleVersion') {{ PAYLOAD.oldDiffParam?.bundleVersion }}
      }
      number('goodsActivityType') {{
        //详情页货架->填单页 玩法枚举code 1:连订
        CONST.baseInfo?.extraMRNParams?.goodsActivityType
      }}
      string('refreshAndCreateOrderExt') {{ NODE.LifecycleLogic?.props?.failPromotion?. refreshAndCreateOrderExt }}
    }
    objectWithSub('relatedOrderParam') {
      string('orderId') {{ NODE.LifecycleLogic?.props?.unPayOrderId }}
      string('relatedOrderId') {{ CONST.baseInfo.oldOrderId ?: CONST.baseInfo.continueLiveOrderId ?: null }}
      bool('reschedule') {{ CONST.baseInfo.isReschedule }}
      bool('continueLiveOrder') {{ CONST.baseInfo.isQuickExtension }}
    }
  }

  currentData {
    string('selectedRedPacketIdentity') {{
      def selectedCoupon = DATA_SOURCE?.data?.promotionVO?.availableCouponVOList?.find {it -> it.selectStatus}
      return selectedCoupon?.couponUserInfoVO?.identity
    }}
    object('discountRights') {{
      // 折扣权益
      def discountRights = DATA_SOURCE.data?.memberVO?.mtMemberVO?.rightsModuleVO?.discountRightsInfoVO
      if (discountRights) {
        return [
          rightsId: discountRights.rightsId,
          rightsCode: discountRights.rightsCode,
          deductionCode: discountRights.deductionCode,
          selectedStatus: true,
        ]
      } else {
        return null
      }
    }}
    object('zjsRights') {{
      // 住就送权益
      def zjsRights = DATA_SOURCE.data?.memberVO?.mtMemberVO?.rightsModuleVO?.displayInfo?.zjsDisPlayModel
      if (zjsRights) {
        return [
          rightsId: zjsRights.rightsId,
          rightsCode: zjsRights.rightsCode,
          deductionCode: zjsRights.deductType,
          selectedStatus: true,
        ]
      } else {
        return null
      }
    }}
    object('jfqedRights') {{
      def memberPoints = DATA_SOURCE.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO
      def activeId = memberPoints?.activeId
      def selectedAsset = memberPoints?.assetStepInfoVOList?.find({ it.selectStatus })
      def isCustomPoint = memberPoints?.useCustomPointsNum ?: false
      def pointsCount = isCustomPoint ? memberPoints?.selectedPointsNum : selectedAsset?.asset
      def discount = isCustomPoint ? memberPoints?.selectedPointsNum : selectedAsset?.amount
      def rightsId = memberPoints?.rightsId
      def rightsCode = memberPoints?.rightsCode

      if (selectedAsset || isCustomPoint) {
       return [[
         activeId: activeId, // 活动id
         pointsCount: pointsCount, // 积分数量
         discount: discount, // 积分金额
         rightsId: rightsId, // 资产的标签id
         rightsCode: rightsCode, // 资产的标签code（对应积分权益code、JFDF、JFQED）
       ]]
      }

      return null
    }}
    object('flagship') {{
      def flagship = DATA_SOURCE.data?.memberVO?.groupMemberVO
      if (!flagship) return null
      return [
        // 是否旗舰店 goods
        groupFlagShipGoods: flagship.groupFlagShipGoods,
        // 是否旗舰店会员
        groupFlagShipMember: flagship.groupFlagShipMember,
        // 会员等级
        groupMemberLevel: flagship.groupMemberLevel,
        // 会员名称
        groupMemberName: flagship.groupMemberName,
        // 是否支持代订
        supportMemberSubscribe: flagship.canSupportMemberSubscribe,
        // 会员价格
        groupMemberDiscountAmount: DATA_SOURCE.data?.priceVO?.groupMemberDiscountAmount,
      ]
    }}
    number('roomCount') {{ DATA_SOURCE.data?.bookInfoVO?.roomCount }}
    number('guestType') {{ DATA_SOURCE.data?.checkinGuestVO?.guestType }}
    string('traceId') {{ DATA_SOURCE.traceId }}
    bool('supportMonthPayPreAuth') {{
      def selectedMagicalCouponPackage = DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule?.couponPackageList?.find {it -> it.selectStatus}
      !selectedMagicalCouponPackage && DATA_SOURCE.data?.paymentVO?.supportMonthPayPreAuth
    }}
    array('createOrderNeedValidateCheckTypes') {{
      // 校验接口需要校验的类型
      DATA_SOURCE.data?.memberVO?.groupMemberVO?.createOrderNeedValidateCheckTypes
    }}
    array('selectedActivityParams') {{
      def selectedActivity = DATA_SOURCE?.data?.promotionVO?.activityVOList ?: []
      def params = selectedActivity?.collect {it -> [id: it.activityId, promotionSource: 0]}
      return params
    }}
    array('selectedCommonCoupons') {{
      def selectedCoupons = DATA_SOURCE?.data?.promotionVO?.availableCouponVOList?.findAll {it -> it.selectStatus}
      def params = selectedCoupons?.collect {it -> [id: it.couponCode, promotionSource: 1, realNameCheck: it.realNameCheck, superGroupCoupon: it.superGroupCoupon]}
      return params
    }}
    array('selectedMagicalCoupons') {{
      def selectedMagicalCoupons = DATA_SOURCE?.data?.promotionVO?.availableMagicalMemberCouponVOList?.findAll {it -> it.selectedStatus}
      def params = selectedMagicalCoupons?.collect {it -> [id: it.couponCode, promotionSource: 1]}
      return params
    }}
    number('selectedPoint') {{
      def pointsNum = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO?.selectedPointsNum
      return pointsNum
    }}
    object('selectedMagicalCouponPackage') {{
      def selectedMagicalCouponPackage = DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule?.couponPackageList?.find {it -> it.selectStatus}
      return selectedMagicalCouponPackage
    }}
    object('selectedInsurance') {{
      def insuranceInfo = DATA_SOURCE.data?.insuranceVO?.insuranceDetailList ?: []

      // 选中保险项目
      def selectedInsurance = insuranceInfo?.find { it.selectStatus == true }
      if (selectedInsurance) {
        return [
          premium: selectedInsurance.premium,
          packageId: selectedInsurance.packageId
        ]
      }
      // 不存在选中保险项目
      return null
    }}
    number('typeLimitValue') {{ DATA_SOURCE.data?.goodsVO?.hourRoomVO?.typeLimitValue }}
    number('roomFeeAmount') {{ DATA_SOURCE?.data?.priceVO?.roomFeeAmount }}
    number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    bool('useCustomPointsNum') {{
      def useCustomPointsNum = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO?.useCustomPointsNum
      return useCustomPointsNum
    }}
    number('totalPromotionAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPromotionAmount }}
    number('totalActivityAmount') {{ DATA_SOURCE?.data?.priceVO?.totalActivityAmount }}
    number('totalCouponAmount') {{ DATA_SOURCE?.data?.priceVO?.totalCouponAmount }}
    string('partnerId') {{ DATA_SOURCE?.data?.merchantVO?.partnerId }}
    string('mboxId') {{ DATA_SOURCE.data?.groupBuyProductVO?.mboxId }}
    string('preGrantId') {{ DATA_SOURCE.data?.groupBuyProductVO?.preGrantId }}
    number('groupBuyProductPayMoney') {{ DATA_SOURCE.data?.groupBuyProductVO?.payAmount }}
    array('groupBuyCouponList') {{ DATA_SOURCE.data?.groupBuyProductVO?.groupBuyCouponList }}
    number('needIdentityNums') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagBookingVO?.needIdentityNums }}
    string('extInfo') {{ DATA_SOURCE?.data?.extendVO?.extInfo ?: '' }}
    string('snapshot') {{ DATA_SOURCE?.data?.extendVO?.snapshot ?: '' }}
    object('linkedBookingInfo') {{
      // 境外酒店联订信息
      def linkedBookingShowInfo = DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO
      return [
        // 联订任务类型
        actionType: linkedBookingShowInfo?.taskCardInfo?.actionType,
        //返现订单状态
        taskOrderStatus: linkedBookingShowInfo?.taskCardInfo?.taskOrderStatus,
      ]
    }}
    number('diffAmount') {{ DATA_SOURCE?.data?.priceVO?.diffAmount }}
    number('beforeCancelRuleMode') {{ DATA_SOURCE?.data?.cancelPolicyVO?.cancelRuleMode }}
    number('identityNumType') {{ DATA_SOURCE?.data?.bookPolicyVO?.identityNumType }}
    bool('needIdentity') {{ DATA_SOURCE?.data?.bookPolicyVO?.needIdentity }}
    number('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId }}
    object('returnPointsParam') {{
      def pointRewardVO = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO?.pointRewardVO

      if (!pointRewardVO) return null

      def returnPointsParam = [
          rewardPoints: pointRewardVO.rewardPoints ?: "0",
          pointsMultiple: pointRewardVO.multiple ?: "0",
          pointsSendTotal: pointRewardVO.totalPoints ?: "0"
      ]

      return returnPointsParam
    }}
    bool('isTourAround') {{
      // 判断是周边游
      !!DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagHeader?.title
    }}
    array('couponBackList') {{ DATA_SOURCE?.data?.promotionVO?.couponBackList }}
    string('stype') {{ DATA_SOURCE?.data?.extendVO?.stype }}
    number('cashRoomFeeAmount') {{ DATA_SOURCE?.data?.priceVO?.cashRoomFeeAmount }}
    number('payType') {{ DATA_SOURCE?.data?.priceVO?.payType }}
    bool('isSuperGroupBuy') {{ DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superDealReservationType == 1 }}
    string('checkInTime') {{
      def checkInPeriodList = DATA_SOURCE?.data?.goodsVO?.hourRoomVO?.checkInPeriodList
      if (checkInPeriodList) {
        def checkInPeriod = checkInPeriodList.find ({it -> !it.checkInNow}) ?: checkInPeriodList[0]
        def checkInTimeStamp = checkInPeriod?.startTimeInterval
        if (checkInTimeStamp && checkInTimeStamp > 0) {
          def timeStr = new Date(checkInTimeStamp + 28800 * 1000).format('yyyy-MM-dd\'T\'HH:mm:ss', TimeZone.getTimeZone('UTC'))
          return timeStr
        }
      }
    }}
    string('checkOutTime') {{
      def checkInPeriodList = DATA_SOURCE?.data?.goodsVO?.hourRoomVO?.checkInPeriodList
      if (checkInPeriodList) {
        def checkInPeriod = checkInPeriodList.find ({it -> !it.checkInNow}) ?: checkInPeriodList[0]
        def checkOutTimeStamp = checkInPeriod?.endTimeInterval
        if(checkOutTimeStamp && checkOutTimeStamp > 1000) {
          def timeStr = new Date(checkOutTimeStamp + 28800 * 1000).format('yyyy-MM-dd\'T\'HH:mm:ss', TimeZone.getTimeZone('UTC'))
          return timeStr
        }
      }
    }}
  }

  bizRespStatus {
    bool('isError') {{
      // 有中断弹窗时没有任何业务数据，按错误处理。
      if (DATA_SOURCE.data?.promptModuleVO?.orderBeforeExceptionPromptInfoVO) {
        return true
      }
      DATA_SOURCE.data == null || DATA_SOURCE.error != null

      // 注意：下面的「加载失败使用默认异常页面」开关需要关闭。
      //   以支持在preview业务失败时，也能走到 @hfe/hotel-submit-lifecycle-logic 组件逻辑。
    }}
    string('errorMsg') {{ DATA_SOURCE.error?.message }}
    object('extra') {{
      def promptModule = DATA_SOURCE.data?.promptModuleVO
      def isExceptionDialog = !!promptModule?.orderBeforeExceptionPromptInfoVO

      def reportCode = DATA_SOURCE.error?.code
      if (reportCode == null) reportCode = DATA_SOURCE.data?.extendVO?.code ?: DATA_SOURCE.data?.code
      reportCode = reportCode != null ? reportCode : -999

      [
        error: DATA_SOURCE.error,
        data: DATA_SOURCE.data ? [
          // 是否通知 poi 刷新
          refreshOrNot: DATA_SOURCE.data?.extendVO?.refreshOrNot,
          // 通知刷新时，根据 code 不同发送不同消息。
          code: DATA_SOURCE.data?.extendVO?.code,
          // 剩余库存是否为0。用于支付取消后，是否需要自动归还库存。
          lastRoomReturnStock: DATA_SOURCE.data?.extendVO?.lastRoomReturnStock,
          // 弹窗
          prompt: promptModule?.previewPromptInfoVO,
          // 异常弹窗，此时页面业务数据是空
          exceptionPrompt: promptModule?.orderBeforeExceptionPromptInfoVO,
        ] : null,
        reportTags: [
          code: reportCode,
          isExceptionDialog: isExceptionDialog,
          bizType: CONST.baseInfo?.bizType ?: -999
        ],
        reportMsg: isExceptionDialog ? '中断弹窗' : DATA_SOURCE.error?.message,
      ]
    }}
    errorToast false
    errorNoReturnStruct false
  }

  submitBizRespStatus {
    bool('isError') {{ DATA_SOURCE.data == null || DATA_SOURCE.error != null }}
    string('errorMsg') {{ DATA_SOURCE.error?.message }}
    object('extra') {{
      def reportCode = DATA_SOURCE.error?.code
      if (reportCode == null) reportCode = DATA_SOURCE.data?.code
      reportCode = reportCode != null ? reportCode : -999

      [
        error: DATA_SOURCE.error,
        data: DATA_SOURCE.data,
        reportTags: [
          code: reportCode,
          bizType: CONST.baseInfo?.bizType ?: -999
        ],
        reportMsg: DATA_SOURCE.error?.message,
      ]
    }}
    errorToast false
  }

  checkBizRespStatus {
    bool('isError') {{ DATA_SOURCE.data == null || DATA_SOURCE.error != null }}
    string('errorMsg') {{ DATA_SOURCE.error?.message }}
    object('extra') {{
      def reportCode = DATA_SOURCE.error?.code
      if (reportCode == null) reportCode = DATA_SOURCE.data?.code
      reportCode = reportCode != null ? reportCode : -999

      [
        error: DATA_SOURCE.error,
        data: DATA_SOURCE.data,
        reportTags: [
          code: reportCode,
          bizType: CONST.baseInfo?.bizType ?: -999
        ],
        reportMsg: DATA_SOURCE.error?.message,
      ]
    }}
    errorToast false
  }
}
