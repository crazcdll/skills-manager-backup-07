node('CommonParams', '757') {
  label 'DUO页面设置组件通用参数'
  props {
    object('lxCommonParams') {{
      [
        cid: CONST.baseInfo.isOversea ? 'hotel_createorder_oversea' : 'c_hotel_createorder_unified',
        channelName: 'hotel',
        pageInfoKey: 'rn_hotel_hotelchannel-orderfill',
        valLab: [
          goods_id: CONST.goodsID ?: '-999',
          poi_id: DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo.poiId ?: '-999',
          shopuuid: DATA_SOURCE?.data?.merchantVO?.shopUuid ?: CONST.baseInfo.shopUuid ?: '-999',
          // 会员等级兜底0
          vip_level: DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel ?: '0',
          partner_id: DATA_SOURCE.data?.merchantVO?.partnerId ?: '-999',
          page_type: CONST.isHourRoom ? '钟点房' : '全日房',
          combined_type: '-999',
          company_vip_level: DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel ?: '-999'
        ],
      ]
    }}
    number('bizType') {{ CONST.baseInfo.bizType }}
    number('goodsId') {{ CONST.goodsID }}
  }
}

node('LifecycleLogicStatic', '1205') {
  label '酒店提单-页面生命周期逻辑(静态)'
}

node('LoadingFill', '1204') {
  label '酒店提单-加载填充骨架屏'
}

node('HfeHotelSubmitPreviewLogic', '847') {
  label '酒店提单-初始化逻辑'
  xIf {{ !CONST.isError }}
  props {
    number('roomNum') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
    number('channelCityId') {{ CONST.baseInfo.extraMRNParams?.channelCityId }}
    number('goodsType') {{ DATA_SOURCE?.data?.goodsVO?.goodsType }}
    string('ctPOI') {{ CONST.baseInfo.ctPoi }}
    string('stID') {{ PAGE_QUERY.stid }}
    string('queryId') {{ CONST.baseInfo.queryId }}
    string('checkIn') {{ CONST.baseInfo.checkin }}
    number('checkInDate') {{ CONST.baseInfo.checkinDate }}
    string('checkOut') {{ CONST.baseInfo.checkout }}
    number('checkOutDate') {{ CONST.baseInfo.checkoutDate }}
    number('superDealType') {{ CONST.baseInfo.superDealSceneType }}
    string('superDealApplyId') {{ CONST.baseInfo.superDealApplyId }}
    number('superDealGoodsType') {{
      def spuExchangeType = DATA_SOURCE.data?.goodsVO?.spuInfoVO?.spuExchangeType
      if (spuExchangeType == 0 || spuExchangeType == 2) {
        return 1
      } else if (spuExchangeType == 1 || spuExchangeType == 3) {
        return 2
      }
      return 0
    }}
    string('mtlm') {{ PAGE_QUERY.mtlm }}
    number('godCouponBusinessType') {{
      def magicalMemberPoiType = DATA_SOURCE.data?.merchantVO?.magicalMemberPoiType
      return magicalMemberPoiType ?: 0
    }}
    string('propagate') {{ PAGE_QUERY.propagate }}
    number('godCouponPoiType') {{ return magicalMemberPoiType ? 1 : 0 }}
    string('spuId') {{ CONST.baseInfo.extraMRNParams?.spuId }}
    number('poiCityId') {{ CONST.baseInfo.poiCityID }}
    string('couponType') {{
      def couponList = (DATA_SOURCE.data?.promotionVO?.availableCouponVOList ?: []) + (DATA_SOURCE.data?.promotionVO?.unavailableCouponVOList ?: [])
      // 1 旧0元通兑 3 新加价通兑
      def type = couponList?.find { item ->
          item.subRedPacketType == 3 || item.subRedPacketType == 1
      }?.subRedPacketType
      return type
    }}
    string('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo.poiId }}
    object('commonParams') {{
      [
        fingerprint: COMMON_PARAMS.fingerprint.fingerprint,
        locationCityId: COMMON_PARAMS.cityInfo.locCityId,
        cityId: COMMON_PARAMS.cityInfo.cityId,
        longitude: COMMON_PARAMS.location.lng,
        latitude: COMMON_PARAMS.location.lat,
      ]
    }}
    number('mtMemberLevel') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel ?: '-999' }}
  }
  on('onKeyBoardShow') {
    callMethod('GuestCard', 'onKeyBoardShow')
    transparentArg('', '')
  }
  on('onKeyBoardShow') {
    callMethod('BottomBar', 'onKeyBoardShow')
  }
  on('onKeyBoardHidden') {
    callMethod('GuestCard', 'onKeyBoardHidden')
    transparentArg('', '')
  }
  on('onKeyBoardHidden') {
    callMethod('BottomBar', 'onKeyBoardHidden')
    transparentArg('', '')
  }
  on('onWindowResize') {
    callMethod('BottomBar', 'onWindowResize')
    transparentArg('', '')
  }
  on('onWindowFocusout') {
    callMethod('BottomBar', 'onWindowFocusout')
    transparentArg('', '')
  }
}

node('LayoutTopBottom', '7') {
  label '页面布局（上中下）'
  xIf {{ !CONST.isError }}
  props {
    bool('statusBarTranslucent') {{ true }}
    string('keyboardAvoidBehavior') {{ COMMON_PARAMS.systemInfo?.platform == 'ios' ? 'padding' : 'height' }}
    number('keyboardVerticalOffset') {{ CONST.keyboardVerticalOffset }}
    string('keyboardShouldPersistTaps') {{ 'handled' }}
    string('keyboardDismissMode') {{ 'none' }}
    bool('hideKeyboardOnScroll') {{ false }}
  }
  style('bottomSafeAreaStyle') {
    string('backgroundColor') {{ '#FFFFFF' }}
  }
  style('scrollStyle') {
    number('paddingLeft') {{ 8 }}
    number('paddingRight') {{ 8 }}
  }
  style('style') {
    string('backgroundColor') {{ '#f5f5f5' }}
  }
  slot('renderTop') {
    node('HfeHotelSubmitNavBar', '819') {
      label '酒店提单-导航栏'
      xIf {{ !COMMON_PARAMS.systemInfo?.envInWeb?.isWebInWeChatMiniProgram }}
      props {
        string('title') {{ DATA_SOURCE?.data?.merchantVO?.poiName }}
        bool('isOversea') {{ CONST.baseInfo.isOversea }}
      }
      on('onPressBack') {
        callMethod('LifecycleLogic', 'closePage')
      }
    }
  }
  slot('renderContent') {
    node('PromptInfo', '890') {
      label '酒店提单页-订单优势规则'
      xIf {{ !!DATA_SOURCE.data?.goodsVO?.roomInfoVO?.roomTagVOList }}
      props {
        bool('defaultHasMFQX') {{ CONST.defaultSelectedRightsCode.contains('MFQX') }}
        array('tags') {{ DATA_SOURCE.data?.goodsVO?.roomInfoVO?.roomTagVOList }}
      }
      on('onCountDownEnd') {
        callMethod('LifecycleLogic', 'update')
      }
    }
    node('MeishiGcLayoutModulesContainer', '748') {
      label '通用模块布局容器组件'
      xIf {{ !CONST.isSuperGroupScene }}
      props {
        number('moduleGap') {{ 0 }}
      }
      style('wrapCardStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
        number('paddingTop') {{ 12 }}
        number('paddingBottom') {{ 10 }}
      }
      slot('renderModules') {
        node('BaseInfo', '800') {
          label '酒店提单-常规头部卡片'
          xIf {{ !!DATA_SOURCE?.data?.bookInfoVO }}
          props {
            object('bookInfoVO') {{ DATA_SOURCE?.data?.bookInfoVO }}
            object('cancelPolicyVO') {{ DATA_SOURCE?.data?.cancelPolicyVO }}
            object('orderAcceptDesc') {{ DATA_SOURCE?.data?.bookPolicyVO?.acceptOrderTag }}
            string('roomName') {{ DATA_SOURCE?.data?.goodsVO?.roomInfoVO?.roomName }}
            array('bookingHintList') {{ DATA_SOURCE?.data?.bookPolicyVO?.bookingHintList }}
            array('roomAttribute') {{ DATA_SOURCE?.data?.goodsVO?.roomInfoVO?.roomAttributeText }}
            object('roomInformation') {{ DATA_SOURCE?.data?.goodsVO?.roomInfoVO?.roomInformationVO }}
            object('spuInfoVO') {{ DATA_SOURCE?.data?.goodsVO?.spuInfoVO }}
            string('giftBagIcon') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagIcon }}
            object('giftBagHeader') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagHeader }}
            object('giftBagDetailVO') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagDetailVO }}
            object('rightsCancelRuleBarBefore') {{
              DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.rightsCancelRuleBarBefore
            }}
            number('checkinPeriod') {{ CONST.defaultBookTimePeriod?.startTimeInterval }}
            bool('defaultHasMFQX') {{ CONST.defaultSelectedRightsCode.contains('MFQX') }}
            bool('isHourRoom') {{ CONST.isHourRoom }}
            bool('isBlindBoxes') {{
              // 1. 酒景购物车 2. 企业微信 3. 店内服务 4. 小微商旅 5. 盲盒一口价
              CONST.baseInfo?.specialChannel == 5
            }}
            string('spuId') {{ CONST.baseInfo?.extraMRNParams?.spuId }}
            number('hotelMemberLevel') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel }}
          }
          style('containerStyle') {
            number('marginBottom') {{ 10 }}
          }
          on('onRoomDetailClickHandler') {
            callMethod('HfeHotelSubmitRoomDetail', 'onOpenModal')
          }
          on('onCancelRuleClickHandler') {
            callMethod('HfeHotelSubmitRoomDetail', 'onOpenModal')
            props {
              string('source') {{ 'cancelServices' }}
            }
            transparentArg('', '')
          }
        }
        node('HfeHotelSubmitBookingRead', '792') {
          label '酒店提单-订房必读'
          xIf {{ !!DATA_SOURCE?.data?.bookPolicyVO?.bookingInformVOList }}
          props {
            array('bookingInformVOList') {{ DATA_SOURCE?.data?.bookPolicyVO?.bookingInformVOList }}
          }
          style('containerStyle') {
            number('marginTop') {{ 10 }}
          }
        }
        node('BookTime', '811') {
          label '酒店提单-入住时段'
          xIf {{ CONST.isHourRoom }}
          props {
            array('checkInPeriodList') {{ DATA_SOURCE?.data?.goodsVO?.hourRoomVO?.checkInPeriodList }}
            object('checkInPeriod') {{ PROPS.checkInPeriod }}
            string('goodsId') {{ CONST.goodsID }}
          }
          propConfig('checkInPeriod') {
            updateBy 'onChangeHourPeriod'
            isRequestArg true
          }
          on('onChangeHourPeriod') {
            callMethod('BaseInfo', 'onUpdateHourRoomCheckinTime')
            transparentArg('', '')
          }
          on('onChangeHourPeriod') {
            callMethod('HfeHotelSubmitTimeRoom', 'updateHourRoomCheckinTime')
            transparentArg('', '')
          }
          buildConfig {
            lazyLoad true
          }
        }
      }
    }
    node('MeishiGcLayoutModulesContainer1', '748') {
      label '通用模块布局容器组件-超团'
      xIf {{ CONST.isSuperGroupScene }}
      props {
        number('moduleGap') {{ 0 }}
      }
      style('wrapCardStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
        number('paddingTop') {{ 12 }}
        number('paddingBottom') {{ 10 }}
      }
      slot('renderModules') {
        node('HfeHotelSubmitSuperdealBaseInfo', '803') {
          label '酒店提单-超团商品基础信息'
          props {
            object('spuInfo') {{ DATA_SOURCE?.data?.goodsVO?.spuInfoVO }}
            object('giftBagHeader') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagHeader }}
            object('giftBagDetailVO') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagDetailVO }}
          }
          style('containerStyle') {
            number('marginBottom') {{ 10 }}
          }
          buildConfig {
            lazyLoad true
          }
        }
        node('HfeHotelSubmitBookingRead1', '792') {
          label '酒店提单-订房必读'
          props {
            array('bookingInformVOList') {{ DATA_SOURCE?.data?.bookPolicyVO?.bookingInformVOList }}
          }
          style('containerStyle') {
            number('marginTop') {{ 10 }}
          }
          buildConfig {
            lazyLoad true
          }
        }
        node('SuperDealBookTime', '811') {
          label '酒店提单-入住时段'
          xIf {{ CONST.isHourRoom }}
          props {
            array('checkInPeriodList') {{ DATA_SOURCE?.data?.goodsVO?.hourRoomVO?.checkInPeriodList }}
            object('checkInPeriod') {{ PROPS.checkInPeriod }}
          }
          propConfig('checkInPeriod') {
            updateBy 'onChangeHourPeriod'
            isRequestArg true
          }
          on('onChangeHourPeriod') {
            callMethod('HfeHotelSubmitTimeRoom', 'updateHourRoomCheckinTime')
            transparentArg('', '')
          }
          buildConfig {
            lazyLoad true
          }
        }
      }
    }
    node('UniversalCalendar', '968') {
      label '酒店提单-门票入园模块（环球影城）'
      xIf {{
        !!DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagBookingVO?.ticketCheckInTimeChooseList?.size()
      }}
      props {
        string('ticketCheckInTime') {{ PROPS.ticketCheckInTime }}
        array('ticketCheckInInfoList') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagBookingVO?.ticketCheckInVOList }}
      }
      propConfig('ticketCheckInTime') {
        updateBy 'onTicketCheckInTimeChange'
        isRequestArg true
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
      on('onUpdate') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('', '')
      }
      on('onScrollTo') {
        callMethod('LayoutTopBottom', 'scrollOffsetY')
        transparentArg('y', 'y')
      }
      buildConfig {
        lazyLoad true
      }
    }
    node('HfeHotelTipBar', '900') {
      label '酒店-紧急提示条'
      xIf {{ !!DATA_SOURCE?.data?.bookPolicyVO?.emergencyNoticeVO?.emergencyNoticeList }}
      props {
        array('textInfos') {{ DATA_SOURCE?.data?.bookPolicyVO?.emergencyNoticeVO?.emergencyNoticeList }}
        string('modalTitle') {{ DATA_SOURCE?.data?.bookPolicyVO?.emergencyNoticeVO?.title }}
        string('orderId') {{ CONST?.baseInfo?.oldOrderId }}
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST?.Module_Gap }}
      }
      buildConfig {
        lazyLoad true
      }
    }
    node('HfeHotelSubmitTimeRoom', '807') {
      label '超团-入住时间房型详情'
      xIf {{ CONST.isSuperGroupScene }}
      props {
        string('checkinTimeText') {{ DATA_SOURCE?.data?.bookInfoVO?.superGroupCheckinTimeText }}
        string('roomInfo') {{ DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.roomInfo }}
        object('cancelRuleDesc') {{ DATA_SOURCE?.data?.cancelPolicyVO?.cancelTimeTag }}
        object('orderAcceptOrderDesc') {{ DATA_SOURCE?.data?.bookPolicyVO?.acceptOrderTag }}
        object('groupBuyReminderDesc') {{ DATA_SOURCE?.data?.bookPolicyVO?.groupBuyReminderTag }}
        bool('isHourRoom') {{ CONST.isHourRoom }}
        number('checkinPeriod') {{ CONST.defaultBookTimePeriod?.startTimeInterval }}
        object('cancelPolicy') {{ DATA_SOURCE?.data?.cancelPolicyVO }}
        string('superDealReservationType') {{ DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superDealReservationType }}
        number('superExchangeType') {{ DATA_SOURCE.data?.goodsVO?.spuInfoVO?.spuExchangeType }}
        string('superDealSceneType') {{ CONST.baseInfo?.superDealSceneType }}
        string('superDealApplyId') {{ CONST.baseInfo?.superDealApplyId }}
        string('resSpuId') {{ CONST.resSpuId }}
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
      on('onCheckinTimeClickHandler') {
        callMethod('LifecycleLogic', 'closePage')
      }
      on('onRoomInfoClickHandler') {
        callMethod('LifecycleLogic', 'closePage')
      }
      buildConfig {
        lazyLoad true
      }
    }
    node('GuestCard', '706') {
      label '酒店提单-住客信息卡片'
      xIf {{ !!DATA_SOURCE?.data?.bookPolicyVO }}
      props {
        array('hintList') {{ DATA_SOURCE?.data?.checkinGuestVO?.guestNameTips }}
        string('roomTip') {{ DATA_SOURCE?.data?.bookPolicyVO?.capacityNote }}
        number('roomNum') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
        number('minNumberOfRooms') {{ DATA_SOURCE?.data?.bookPolicyVO?.minNumberOfRooms }}
        number('maxNumberOfRooms') {{ DATA_SOURCE?.data?.bookPolicyVO?.maxNumberOfRooms }}
        array('selectedSuperCouponList') {{ CONST.selectedSuperCouponList }}
        number('guestType') {{ DATA_SOURCE?.data?.checkinGuestVO?.guestType }}
        array('supportedIdentityType') {{ DATA_SOURCE?.data?.bookPolicyVO?.supportedIdentityTypeList }}
        string('identityNumType') {{ DATA_SOURCE?.data?.bookPolicyVO?.identityNumType }}
        bool('isTourAround') {{ CONST.isTourAround }}
        number('adultNum') {{ CONST.baseInfo.adultNum }}
        array('guestInfo') {{ PROPS.guestInfo }}
        bool('canOneGuest') {{ DATA_SOURCE?.data?.bookPolicyVO?.canOneGuest }}
        object('antiCrawlParams') {{
          [
            propagate: CONST.baseInfo.propagate,
            page_source: CONST.baseInfo.extraMRNParams?.page_source,
            poiId: DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo?.poiId,
            shopuuid: DATA_SOURCE?.data?.merchantVO?.shopUuid ?: CONST.baseInfo.extraMRNParams?.shopuuid,
          ]
        }}
        string('goodsId') {{ CONST.goodsID }}
        string('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo.poiId }}
        number('needIdentityNumsOfTourAround') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagBookingVO?.needIdentityNums }}
        bool('hasSelectedLimitCoupon') {{ CONST.hasSelectedLimitCoupon }}
        string('phoneNum') {{
          PROPS.phoneNum != null ? PROPS.phoneNum : DATA_SOURCE?.data?.checkinGuestVO?.phone
        }}
        object('countryCode') {{
          def apiDefault = DATA_SOURCE?.data?.checkinGuestVO?.countryCallingCode
          def otherDefault = '86'
          def Key =  PROPS.countryCode?.Key ?: apiDefault ?: otherDefault
          return [ Key: Key ]
        }}
        string('earliestCheckInTimeDesc') {{ DATA_SOURCE?.data?.goodsVO?.earlyCheckinTimeText }}
        array('arriveTimeList') {{ DATA_SOURCE?.data?.bookPolicyVO?.arriveTimeList }}
        number('payType') {{ DATA_SOURCE?.data?.priceVO?.payType }}
        bool('isQuickExtension') {{ CONST.baseInfo.isQuickExtension }}
        object('arriveTimeObj') {{
          PROPS.arriveTimeObj != null ? PROPS.arriveTimeObj : DATA_SOURCE?.data?.bookPolicyVO?.arriveTimeList?.find { it?.defaultCheck == true }
        }}
        string('roomNo') {{ PROPS.roomNo != null ? PROPS.roomNo : CONST.baseInfo.roomNo }}
        string('partnerId') {{ DATA_SOURCE.data.merchantVO?.partnerId }}
        number('schemeSpecialChannel') {{ CONST.baseInfo?.specialChannel }}
        string('email') {{ PROPS.email  != null ? PROPS.email : DATA_SOURCE?.data?.checkinGuestVO?.email }}
        bool('isInland_ZL') {{ CONST.baseInfo.isInland_ZL }}
        bool('isOversea') {{ CONST.baseInfo.isOversea }}
        object('defaultGuestInfo') {{ DATA_SOURCE?.data?.checkinGuestVO?.guestVOList?.getAt(0) }}
        string('token') {{ COMMON_PARAMS.userInfo?.token }}
        string('userId') {{ COMMON_PARAMS.userInfo?.userId }}
        number('keyboardVerticalOffset') {{ CONST.keyboardVerticalOffset }}
        number('childNum') {{ CONST.baseInfo.childNum ?: 0 }}
        bool('isUniversal') {{
          !!DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagBookingVO?.ticketCheckInTimeChooseList?.size()
        }}
        array('identityModels') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagBookingVO?.identityModels }}
        bool('groupFlagShipMember') {{ !!DATA_SOURCE.data?.memberVO?.groupMemberVO?.groupFlagShipMember }}
      }
      propConfig('phoneNum') {
        updateBy 'onChangePhoneNum'
        isRequestArg true
        lock false
      }
      propConfig('guestInfo') {
        updateBy 'onChangeGuestInfo'
        isRequestArg true
      }
      propConfig('countryCode') {
        updateBy 'onChangeCountryCode'
        isRequestArg true
        lock false
      }
      propConfig('roomNo') {
        updateBy 'onChangeRoomNo'
        isRequestArg true
        lock false
      }
      propConfig('email') {
        updateBy 'onChangeEmail'
        isRequestArg true
      }
      propConfig('arriveTimeObj') {
        updateBy 'onChangeArriveTime'
        isRequestArg true
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
      on('onUpdateRoomNum') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('value', 'payload.roomNum')
        transparentArg('refreshPromotion', 'payload.refreshPromotion')
        transparentArg('refreshMagicalCouponPackage', 'payload.refreshMagicalCouponPackage')
      }
      on('onChangeEmail') {
        callMethod('HfeHotelSubmitPrePay', 'onChangeGuestEmail')
        transparentArg('', 'guestEmail')
      }
      on('onChangeGuestList') {
        callMethod('LifecycleLogic', 'changeGuestList')
        transparentArg('', 'guestList')
      }
      on('onChangeGuestList') {
        callMethod('HfeHotelSubmitPrePay', 'onChangeGuestInfo')
        transparentArg('', 'guestList')
      }
      on('onChangeGuestList') {
        callMethod('RegisterFlagshipMember', 'changeGuestInfo')
        transparentArg('0', 'guestList')
        transparentArg('1', 'isAutoChange')
      }
      on('onChangeGuestList') {
        callMethod('InsuranceTying', 'onUpdateInsuranceShowStatus')
        transparentArg('', 'guestList')
      }
      on('onScrollTo') {
        callMethod('LayoutTopBottom', 'scrollOffsetY')
        transparentArg('y', 'y')
      }
      on('onChangePhoneNum') {
        callMethod('HfeHotelSubmitPrePay', 'onChangeGuestPhone')
        transparentArg('', 'phoneNum')
      }
      on('onChangePhoneNum') {
        callMethod('RegisterFlagshipMember', 'changePhone')
        transparentArg('', 'phone')
      }
      on('onSetKeyboardVerticalOffset') {
        callMethod('LayoutTopBottom', 'onSetKeyboardVerticalOffset')
        transparentArg('', 'offset')
      }
      on('onIdentityChange') {
        callMethod('RegisterFlagshipMember', 'updateMemberIdentity')
        transparentArg('', 'identity')
      }
    }
    node('OverseaMultipleTask', '918') {
      label '酒店提单-境外(省钱任务/多单返现)'
      xIf {{
        CONST.baseInfo.isOversea && !!DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO
      }}
      props {
        number('finalPayPrice') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
        number('giveUpDiscountPrice') {{ DATA_SOURCE?.data?.priceVO?.linkedAmountVO?.payAmountExceptLinkedDiscount }}
        array('taskActiveInfoList') {{ DATA_SOURCE.data?.promotionVO?.taskActivityVOList ?: [] }}
        object('linkedBookingShowInfo') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO }}
        bool('isSelectedTaskCard') {{
          PROPS.isSelectedTaskCard ?: CONST.baseInfo.extraMRNParams?.isMultiOrderDiscountSelected ?: false
        }}
      }
      propConfig('isSelectedTaskCard') {
        updateBy 'onTaskCardSelectedChange'
        isRequestArg true
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
      on('onUpdate') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('', '')
      }
      buildConfig {
        lazyLoad true
      }
    }
    node('PromotionModulesContainer', '748') {
      label '通用模块布局容器组件'
      xIf {{ CONST.promotionShow.isShow }}
      props {
        string('dividerType') {{ 'gap' }}
        number('moduleGap') {{ 16 }}
      }
      style('wrapCardStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
        number('paddingTop') {{ 12 }}
        number('paddingBottom') {{ 12 }}
        number('paddingLeft') {{ 12 }}
        number('paddingRight') {{ 12 }}
        number('borderRadius') {{ CONST.Module_BorderRadius }}
      }
      slot('renderModules') {
        node('PromotionNormalHeader', '38') {
          label '营销卡片-普通头部标题'
          xIf {{ CONST.promotionShow.isShowNormalHeader }}
          props {
            string('type') {{ 'title3' }}
            string('color') {{ '#111111' }}
            string('text') {{ '本单可享' }}
          }
          style('style') {
            number('marginTop') {{ 1 }}
            number('marginBottom') {{ -2 }}
          }
        }
        node('PromotionMemberHeader', '774') {
          label '酒店提单-营销卡片-会员头'
          xIf {{ CONST.promotionShow.isShowMemberHeader }}
          props {
            number('memberLevel') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel }}
            number('subLevel') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.subLevel }}
            string('subLevelTextColor') {{
              DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.titleShow?.subLevelTextColor
            }}
            string('titleImg') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.titleShow?.titleImg }}
            string('backgroundImg') {{
              DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.titleShow?.backgroundImg
            }}
            string('subLevelLitStar') {{
              DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.titleShow?.subLevelLitStar
            }}
            string('subLevelUnlitStar') {{
              DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.titleShow?.subLevelUnlitStar
            }}
          }
        }
        node('PromotionDiscountCard', '784') {
          label '酒店提单-优惠模块'
          xIf {{ CONST.promotionShow.isShowDiscountCard }}
          props {
            number('bizType') {{ CONST.baseInfo.bizType }}
            number('goodsID') {{ CONST.goodsID }}
            number('channelCityID') {{ CONST.baseInfo.channelCityID }}
            number('poiCityID') {{ CONST.baseInfo.poiCityID }}
            number('adultNum') {{ CONST.baseInfo.adultNum }}
            object('magicalMemberModule') {{ DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule }}
            object('promotionVO') {{
              def promotionInfo = DATA_SOURCE?.data?.promotionVO

              if (!promotionInfo) return null

              return [
                activityVOList: promotionInfo?.activityVOList,
                availableCouponVOList: promotionInfo?.availableCouponVOList,
                unavailableCouponVOList: promotionInfo?.unavailableCouponVOList,
                availableMagicalMemberCouponVOList: promotionInfo?. availableMagicalMemberCouponVOList,
                unavailableMagicalMemberVOCouponList: promotionInfo?.unavailableMagicalMemberVOCouponList,
                promotionTipVO: promotionInfo?.promotionTipVO,
                magicalMemberExtendInfoVO: promotionInfo?.magicalMemberExtendInfoVO,
                promotionLockPairs: promotionInfo?.promotionLockPairs
              ]
            }}
            object('priceVO') {{
              def priceInfo = DATA_SOURCE?.data?.priceVO

              if (!priceInfo) return null

              return [
                 totalPromotionAmount: priceInfo.totalPromotionAmount,
                 roomFeeAmount: priceInfo.roomFeeAmount,
                 cashBackAmount: priceInfo.cashBackTotalAmount,
                 totalPayAmount: priceInfo.totalPayAmount,
              ]
            }}
            object('merchantVO') {{
              def merchantInfo = DATA_SOURCE?.data?.merchantVO

              if (!merchantInfo) return null

              return [
                 poiId: merchantInfo.poiId,
                 shopId: merchantInfo.shopId,
                 magicalMemberPoiType: merchantInfo.magicalMemberPoiType,
              ]
            }}
            object('jfqedPointInfo') {{
              def memberPoints = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO

              def mtMemberLevel = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel

              def rightsType = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO?.rightsType

              def assetStepInfoVOList = memberPoints?.assetStepInfoVOList ?: []
              if (!assetStepInfoVOList) return null

              def availablePoints = memberPoints?.availablePoints
              def assetExchange = memberPoints?.pointsAssetExchange
              def jfqedPoint = memberPoints?.selectedPointsNum
              def userCustomPointsNum = memberPoints?.useCustomPointsNum
              def hasCustom = assetStepInfoVOList.size() >= 3

              def assetStepInfos = [[
                asset: 0,
                discount: 0,
                desc: '暂不使用积分',
              ], *assetStepInfoVOList]

              if(hasCustom) {
                assetStepInfos.add([
                  desc: '自定义使用积分数量',
                  selectStatus: userCustomPointsNum,
                  asset: jfqedPoint,
                  amount: jfqedPoint,
                  code: 'custom'
                ])
              }

              return [
                assetStepInfos: assetStepInfos,
                availablePoints: availablePoints,
                assetExchange: assetExchange,
                jfqedPoint: jfqedPoint,
                userCustomPointsNum: userCustomPointsNum,
                mtMemberLevel: mtMemberLevel,
                rightsType: rightsType
              ]
            }}
            number('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo.poiId }}
            number('roomCount') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
            number('checkInTimestamp') {{ CONST.baseInfo.checkinDate }}
            number('checkOutTimestamp') {{ CONST.baseInfo.checkoutDate }}
            string('cityId') {{ COMMON_PARAMS?.cityInfo?.cityId }}
            number('lat') {{ COMMON_PARAMS?.location?.lat }}
            number('lng') {{ COMMON_PARAMS?.location?.lng }}
            string('dpid') {{ COMMON_PARAMS?.userInfo?.dpid }}
            number('traceID') {{ DATA_SOURCE?.traceId }}
            bool('isOnlyShowPromotion') {{ CONST.promotionShow?.isOnlyShowPromotion }}
            bool('needSelectMagicalMemberCoupon') {{ PROPS.needSelectMagicalMemberCoupon }}
            bool('useVoucherPosition') {{ PROPS.useVoucherPosition }}
            bool('noUseSuperDealCoupon') {{ PROPS.noUseSuperDealCoupon }}
            object('miniProgramParams') {{
              if (COMMON_PARAMS.systemInfo?.isMRN) return null
              def IS_DP = COMMON_PARAMS?.systemInfo?.IS_DP
              def queryParams = [
                token: COMMON_PARAMS.userInfo?.token,
                userid: COMMON_PARAMS.userInfo?.userId,
                platformid: IS_DP ? 2 : 1,
                utm_campaign: IS_DP ? 'ADianpingBADianpingBnullC0E0' : 'AgroupBgroup'
              ]
              [
                uuid: COMMON_PARAMS.userInfo?.uuid,
                versionName: COMMON_PARAMS.systemInfo.mpAppVersion,
                openId: COMMON_PARAMS.userInfo?.openId,
                appId: COMMON_PARAMS.systemInfo?.mpAppId,
                fingerprint: COMMON_PARAMS.fingerprint?.fingerprint,
                pageCityId: COMMON_PARAMS.cityInfo.cityId,
                queryParams: queryParams
              ]
                
            }}
          }
          propConfig('needSelectMagicalMemberCoupon') {
            updateBy 'onNeedSelectMagicalMemberCouponUpdated'
            isRequestArg true
          }
          propConfig('useVoucherPosition') {
            updateBy 'onUseVoucherPosition'
            isRequestArg true
          }
          propConfig('noUseSuperDealCoupon') {
            updateBy 'onNoUseSuperDealCouponUpdate'
            isRequestArg true
          }
          on('onPromotionUpdated') {
            callMethod('LifecycleLogic', 'update')
            transparentArg('selectedMagicalCoupons', 'payload.selectedMagicalCoupons')
            transparentArg('magicalCouponPackageParams', 'payload.magicalCouponPackageParams')
            transparentArg('eachInflateParams', 'payload.eachInflateParams')
            transparentArg('fromPromotion', 'payload.fromPromotion')
            transparentArg('selectedCommonCoupons', 'payload.selectedCommonCoupons')
            transparentArg('refreshPromotion', 'payload.refreshPromotion')
            transparentArg('onResponse', 'onResponse')
            transparentArg('refreshMagicalCouponPackage', 'payload.refreshMagicalCouponPackage')
          }
          on('onJfqedPointUpdated') {
            callMethod('LifecycleLogic', 'update')
            transparentArg('pointsNum', 'payload.pointsNum')
            transparentArg('useCustomPointsNum', 'payload.useCustomPointsNum')
          }
          on('onPromotionDiscountClick') {
            callMethod('HfeHotelSubmitPreviewLogic', 'onUpdateCouponStatus')
            transparentArg('', '')
          }
        }
        node('HfeHotelSubmitReturnAfterCheckin', '932') {
          label '酒店提单-入住后返'
          xIf {{ CONST.promotionShow.isShowCheckinBack }}
          props {
            string('title') {{
              DATA_SOURCE.data?.promotionVO?.promotionTipVO?.cashBackShowTipVO?.promotionPrompt?.title
            }}
            string('text') {{
              DATA_SOURCE.data?.promotionVO?.promotionTipVO?.cashBackShowTipVO?.promotionPrompt?.text
            }}
            string('modalTitle') {{
              DATA_SOURCE.data?.promotionVO?.promotionTipVO?.cashBackShowTipVO?.promotionPrompt?.commonPopupsVO?.title
            }}
            number('cashBackTotalAmount') {{ DATA_SOURCE.data?.priceVO?.linkedAmountVO?.totalCashBackAmountExceptLinked }}
            string('currencySymbol') {{ DATA_SOURCE.data?.priceVO?.currencySymbol ?: '¥' }}
          }
          buildConfig {
            lazyLoad true
          }
        }
        node('Rights', '759') {
          label '酒店提单-会员权益'
          xIf {{ CONST.promotionShow.isShowRights }}
          props {
            number('roomCount') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
            number('mtMemberLevel') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel }}
            object('rightsModule') {{
              def rightsModule = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO

              if (!rightsModule) return null

              // 剔除不使用的字段，优化传输体积
              return [
                *: rightsModule,
                reservationRuleVO: null,
                memberPointsVO: rightsModule.memberPointsVO ? [
                  availablePoints: rightsModule.memberPointsVO.availablePoints,
                  totalDiscountAmount: rightsModule.memberPointsVO.totalDiscountAmount,
                ] : null,
                displayInfo: null,
                discountRightsInfoVO: null,
                studentLiveNFreeOne: null,
                rightTags: null,
                rightCancelRuleBarBefore: null,
              ]
            }}
            object('value') {{ PROPS.value }}
          }
          propConfig('value') {
            updateBy 'onChange'
            isRequestArg true
          }
          on('onChange') {
            callMethod('LifecycleLogic', 'selectRightsChange')
            transparentArg('selected', 'selectRights')
          }
          on('onChange') {
            callMethod('StayGift', 'updateSelectedRightsCode')
            transparentArg('selected', 'selectRights')
          }
          on('onMFQXUserSelectChange') {
            callMethod('PromptInfo', 'onMFQXUserSelectChange')
            transparentArg('', '')
          }
          on('onMFQXUserSelectChange') {
            callMethod('BaseInfo', 'onUpdateHasMFQX')
            transparentArg('', '')
          }
        }
        node('HfeHotelSubmitMutiOrderCashBack', '931') {
          label '酒店提单-境外多单返现'
          xIf {{ CONST.promotionShow.isShowOverseaCashBack }}
          props {
            string('currencySymbol') {{ DATA_SOURCE?.data?.priceVO?.currencySymbol ?: '' }}
            number('multiOrderCashback') {{ DATA_SOURCE?.data?.priceVO?.linkedAmountVO?.overseaHotelCashBackTotalAmount }}
            object('taskDiscountDescInfo') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO?.taskDiscountDescInfo }}
          }
          buildConfig {
            lazyLoad true
          }
        }
        node('StayGift', '773') {
          label '酒店提单-住就送'
          xIf {{ CONST.promotionShow.isShowStayGift }}
          props {
            object('zjsDisPlayModel') {{
              DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.displayInfo?.zjsDisPlayModel
            }}
            array('defaultSelectedRightsCode') {{ CONST.defaultSelectedRightsCode }}
            string('userId') {{ COMMON_PARAMS.userInfo.userId }}
            string('token') {{ COMMON_PARAMS.userInfo.token }}
          }
        }
        node('MemberPoints', '1028') {
          label '酒店提单-离店积分'
          xIf {{ CONST.promotionShow.isShowMemberPoints }}
          props {
            object('memberPointsVO') {{
              def memberPoints = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.memberPointsVO
              if (!memberPoints) return null
              return [
                *: memberPoints,
                rightsInfoVO: null,
              ]
            }}
            bool('isOversea') {{ CONST.baseInfo.isOversea }}
            string('hotelMemberLevel') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel }}
          }
        }
        node('InlandMultipleTask', '927') {
          label '酒店提单-国内连订任务'
          xIf {{
            CONST.promotionShow.isShowinlandCashBack || CONST.promotionShow.isShowInlandNewLinkedTask
          }}
          props {
            array('taskCardVOList') {{ DATA_SOURCE.data?.promotionVO?.taskCardVOList }}
            array('taskActiveInfoList') {{ DATA_SOURCE.data?.promotionVO?.taskActivityVOList ?: [] }}
            object('linkedBookingShowInfo') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO }}
            array('linkedCheckList') {{ PROPS.linkedCheckList }}
            bool('selectedLinkedTaskCacheIsValid') {{ CONST.selectedLinkedTaskFromCache?.isValid }}
            array('newLinkedTaskList') {{ DATA_SOURCE.data?.promotionVO?.linkedBookingTaskVO?.taskCardVOList }}
            string('multiLinkedTaskCombineInfo') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingTaskVO?.multiTaskCombineInfo }}
            bool('showNewLinkedTaskStyle') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingTaskVO?.newCombineStyle }}
            string('userId') {{ COMMON_PARAMS.userInfo?.userId }}
          }
          propConfig('linkedCheckList') {
            updateBy 'onUpdateLinkedCheckList'
            isRequestArg true
          }
          on('onUpdate') {
            callMethod('LifecycleLogic', 'update')
            transparentArg('', '')
          }
          on('onToggleLinkedTask') {
            callMethod('HfeHotelSubmitBottomToolTipBar', 'onLinkedTaskChange')
            transparentArg('', '')
          }
          on('onScrollTo') {
            callMethod('LayoutTopBottom', 'scrollOffsetY')
            transparentArg('y', 'y')
          }
          on('onMultiDiscountBottomBarChange') {
            callMethod('BottomBar', 'onMultiDiscountBottomBarChange')
            transparentArg('', '')
          }
        }
        node('HfeHotelSubmitOrderGift', '1021') {
          label '酒店提单页-境外礼包列表'
          xIf {{
            def couponBackList = DATA_SOURCE?.data?.promotionVO?.couponBackList

            def giftBagTicketList = DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagTicketVO

            return couponBackList || giftBagTicketList
          }}
          props {
            array('giftList') {{
              def couponBackList = DATA_SOURCE?.data?.promotionVO?.couponBackList
              def giftBagTicketVO = DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagTicketVO

              def giftBagTicketList = giftBagTicketVO ? [giftBagTicketVO] : []

              return (couponBackList ?: []) + giftBagTicketList
            }}
            number('bizType') {{ DATA_SOURCE?.data?.bizType }}
          }
          style('containerStyle') {
            number('paddingTop') {{ 6 }}
            number('paddingBottom') {{ 6 }}
          }
          buildConfig {
            lazyLoad true
          }
        }
      }
    }
    node('HfeHotelSubmitEndComp', '1091') {
      label '酒店提单-首屏结束最后一个组件'
    }
    node('MarriottMemberCard', '857') {
      label '酒店提单-万豪会员卡片'
      xIf {{
        def groupMemberInfo = DATA_SOURCE?.data?.memberVO?.groupMemberVO
        return groupMemberInfo?.groupCardInfo && groupMemberInfo?.groupMemberLevelName
      }}
      props {
        object('groupMemberVO') {{
          def groupMemberInfo = DATA_SOURCE?.data?.memberVO?.groupMemberVO
          [
            groupMemberLevelName: groupMemberInfo?.groupMemberLevelName,
            memberInfo: groupMemberInfo?.memberInfo,
            taskChallengeInfo: groupMemberInfo?.taskChallengeInfo,
            groupCardInfo: groupMemberInfo?.groupCardInfo,
            memberToastInfo: groupMemberInfo?.memberToastInfo,
          ]
        }}
        bool('signUpFlagship') {{ PROPS.signUpFlagship }}
      }
      propConfig('signUpFlagship') {
        updateBy 'onChangeSignUpFlagship'
        isRequestArg true
      }
      on('onClickToastLeftBtn') {
        callMethod('LifecycleLogic', 'closePageWithNotifyPoi')
      }
      buildConfig {
        lazyLoad true
      }
    }
    node('MagicalCouponPackage', '791') {
      label '酒店提单-神会员搭售券包'
      xIf {{ !!DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule }}
      props {
        number('bizType') {{ CONST.baseInfo.bizType }}
        number('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST?.baseInfo?.poiId }}
        number('goodsID') {{ CONST.goodsID }}
        object('magicalMemberModule') {{ DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule }}
      }
      on('onMagicalCouponPackageSelect') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('magicalCouponPackageParams', 'payload.magicalCouponPackageParams')
        transparentArg('refreshPromotion', 'payload.refreshPromotion')
        transparentArg('fromPromotion', 'payload.fromPromotion')
      }
      on('onScrollTo') {
        callMethod('LayoutTopBottom', 'scrollOffsetY')
        transparentArg('y', 'y')
      }
      on('onToggleMMCTip') {
        callMethod('HfeHotelSubmitBottomToolTipBar', 'onToggleMMCTip')
        transparentArg('', '')
      }
      on('onUseVoucherPositionChange') {
        callMethod('PromotionDiscountCard', 'onUseVoucherPositionChange')
        transparentArg('', 'value')
      }
    }
    node('HfeHotelSubmitLiveNFreeX', '756') {
      label '住N送X组件'
      xIf {{
        COMMON_PARAMS.systemInfo.isMRN && !!DATA_SOURCE?.data?.memberVO?.mtMemberVO?.task4OrderModuleVO?.taskShow4Order
      }}
      props {
        object('userTaskVO') {{
          /**
           * 获取用户任务信息
           * 如果 userTaskVO 为字符串，则解析为对象，否则直接返回原始值
           */
          def userTaskVO = DATA_SOURCE?.data?.memberVO?.mtMemberVO?.task4OrderModuleVO?.taskShow4Order

          def resultTaskVO = userTaskVO instanceof String ? DF.jsonParse(userTaskVO ?: '{}') : userTaskVO
          resultTaskVO
        }}
        string('sourcePage') {{ 'hotel_orderfill' }}
        object('lxValParams') {{
          return [
            vip_level: DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel ?: 0,
            goods_id: CONST?.goodsID ?: '-999',
            poi_id: CONST?.baseInfo?.poiId ?: '-999',
            order_id: '-999'
            ]
        }}
      }
      style('contentStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
      on('refreshPage') {
        callMethod('LifecycleLogic', 'update')
      }
      buildConfig {
        lazyLoad true
      }
    }
    node('RoomUpgrade', '844') {
      label '酒店提单-房型升级'
      xIf {{ COMMON_PARAMS.systemInfo.isMRN && !!DATA_SOURCE?.data?.extendVO?.roomUpgrade }}
      props {
        bool('isChecked') {{ PROPS.isChecked }}
        number('recommendedGoodsId') {{ PROPS.recommendedGoodsId }}
        string('goodsID') {{
          // 房型升级前的 goodsID
          PAGE_QUERY.goods_id
        }}
        number('bizType') {{ CONST.baseInfo.bizType }}
        number('roomNum') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
        number('numberOfDays') {{ DATA_SOURCE?.data?.bookInfoVO?.nightCount }}
        string('checkin') {{ CONST.baseInfo.checkin }}
        string('checkout') {{ CONST.baseInfo.checkout }}
        number('adultNum') {{ CONST.baseInfo.adultNum }}
        array('childAge') {{ CONST.baseInfo.childAge }}
        number('originPayPrice') {{
          // 房型升级后，接口不再返回升级前的价格，需要模块保存下来之前的价格
          if (CONST.isRoomUpgrade) {
            return PROPS.originPayPrice
          }
          def priceInfo = DATA_SOURCE?.data?.priceVO
          if (priceInfo) {
            return (priceInfo.roomFeeAmount ?: 0) - (priceInfo.totalPromotionAmount ?: 0)
          }
          return 0
        }}
        string('lat') {{ COMMON_PARAMS?.location?.lat }}
        string('lng') {{ COMMON_PARAMS?.location?.lng }}
        string('userId') {{ COMMON_PARAMS?.userInfo?.userId }}
        string('token') {{ COMMON_PARAMS?.userInfo?.token }}
        object('extraMRNParams') {{
          def baseInfo = CONST.baseInfo
          def params = baseInfo?.extraMRNParams
          if (!params) return null
          return [
            poiId: params.poiId,
            fromOffline: baseInfo.fromOffline,
            goodsIds: params.goodsIds,
            underLineShopSell: baseInfo.underLineShopSell,
            originGoodsStatus: baseInfo.originGoodsStatus,
          ]
        }}
        string('specAttributionChannel') {{
          PAGE_QUERY?.specAttributionChannel ?: CONST.baseInfo.extraMRNParams?.specAttributionChannel ?: ''
        }}
      }
      propConfig('originPayPrice') {
        isRequestArg true
      }
      propConfig('isChecked') {
        updateBy 'onChange'
        isRequestArg true
      }
      propConfig('recommendedGoodsId') {
        updateBy 'onRecommendedGoodsId'
        isRequestArg true
      }
      on('onChange') {
        callMethod('LayoutTopBottom', 'scrollTo')
        props {
          number('y') {{ 0 }}
        }
      }
      on('onUpdate') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('', '')
      }
      on('onRecommendedGoods') {
        callMethod('LifecycleLogic', 'changeRoomUpgradeType')
        transparentArg('RoomUpgradeInfo.type', 'type')
      }
      on('onPriceDiff') {
        callMethod('LifecycleLogic', 'changeRoomUpgradePriceDiff')
        transparentArg('', 'priceDiff')
      }
      on('onPress') {
        callMethod('HfeHotelSubmitRoomDetail', 'onOpenModal')
        props {
          string('from') {{ 'room_upgrade' }}
        }
        transparentArg('', 'roomUpgradeDetailInfo')
      }
    }
    node('InsuranceTying', '704') {
      label '酒店提单-保险搭售'
      xIf {{ !!DATA_SOURCE?.data?.insuranceVO }}
      props {
        object('allInsuredPersonList') {{ PROPS.allInsuredPersonList }}
        number('roomNum') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
        bool('hasSelectedLimitCoupon') {{ CONST.hasSelectedLimitCoupon }}
        bool('ticketCount') {{ DATA_SOURCE?.data?.goodsVO?.giftBagVO?.giftBagBookingVO?.needIdentityNums }}
        bool('isTourAround') {{ CONST.isTourAround }}
        string('identityNumType') {{ DATA_SOURCE?.data?.bookPolicyVO?.identityNumType }}
        number('adultNum') {{ CONST.baseInfo.adultNum }}
        object('insuranceInfo') {{ DATA_SOURCE?.data?.insuranceVO }}
        object('forwardedParams') {{
          // guestType固定1
          [
              salePrice: DATA_SOURCE?.data?.priceVO?.roomFeeAmount,
              poiId: DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST?.baseInfo?.poiId,
              roomNum: roomNum,
              bizType: CONST.baseInfo.bizType,
              goodsId: CONST.goodsID,
              guestNum: guestNum,
              guestType: 1,
              nameHintList: DATA_SOURCE?.data?.checkinGuestVO?.guestNameTips,
          ]
        }}
      }
      propConfig('allInsuredPersonList') {
        updateBy 'onChangeInsuredPersonList'
        isRequestArg true
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
      on('onUpdate') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('', '')
      }
      on('onScrollTo') {
        callMethod('LayoutTopBottom', 'scrollOffsetY')
        transparentArg('y', 'y')
      }
    }
    node('HfeHotelSubmitPrePay', '778') {
      label '酒店提单-前置支付'
      xIf {{
        if (!COMMON_PARAMS.systemInfo.isMRN) return false

        def payType = DATA_SOURCE.data.priceVO?.payType
        def superDealBooking = DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superDealReservationType == 1
        def payFeeCent = superDealBooking ? DATA_SOURCE?.data?.priceVO?.groupBuyPayAmount : DATA_SOURCE.data.priceVO?.totalPayAmount

        return (!CONST.baseInfo.isOfflineVIP
          && payType != 2
          && payType != 3
          && !!payFeeCent
          && (payFeeCent as Double) > 0)
      }}
      props {
        object('prePayInfo') {{ PROPS.prePayInfo }}
        object('baseInfo') {{
          [
            isOfflineVIP: CONST.baseInfo.isOfflineVIP,
            isOversea: CONST.baseInfo.isOversea,
            poiCityID: CONST.baseInfo.poiCityID,
            checkinDate: CONST.baseInfo.checkinDate,
            checkoutDate: CONST.baseInfo.checkoutDate,
            checkin: CONST.baseInfo.checkin,
            checkout: CONST.baseInfo.checkout,
            applyId: CONST.baseInfo.applyId,
            extraMRNParams: CONST.baseInfo.extraMRNParams,
          ]
        }}
        string('userId') {{ COMMON_PARAMS?.userInfo?.userId }}
        object('selectedMagicMemberCouponPackage') {{
          DATA_SOURCE.data.couponPackageVO?.magicalMemberModule?.couponPackageList?.find { it.selectStatus } ?: [:]
        }}
        string('goodsID') {{ CONST.goodsID }}
        number('roomNum') {{ DATA_SOURCE.data.bookInfoVO?.roomCount }}
        string('payFeeCent') {{
          // 超团立即预订
          def superDealBooking = DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superDealReservationType == 1
          return superDealBooking ? DATA_SOURCE?.data?.priceVO?.groupBuyPayAmount : DATA_SOURCE.data.priceVO?.totalPayAmount
        }}
        string('poiId') {{ DATA_SOURCE.data.merchantVO?.poiId ?: CONST?.baseInfo?.poiId }}
        string('poiName') {{ DATA_SOURCE.data.merchantVO?.poiName }}
        string('orderType') {{ DATA_SOURCE.data.extendVO?.orderType }}
        string('orderAmount') {{ DATA_SOURCE.data.priceVO?.roomFeeAmount }}
        string('merReduce') {{
          // 老版接口字段后端无实现，一直为0
          0
        }}
        string('roomName') {{ DATA_SOURCE.data.goodsVO?.roomInfoVO?.roomName }}
        object('paymentInfo') {{
          def paymentVO = DATA_SOURCE.data?.paymentVO
          [
            supportMonthPayPreAuth: paymentVO?.supportMonthPayPreAuth,
            preCashierScene: paymentVO?.preCashierScene,
            preCashierId: paymentVO?.preCashierId,
            sellerId: paymentVO?.merchantNo
          ]
        }}
        bool('hasInsurance') {{ DATA_SOURCE.data.insuranceVO?.insuranceDetailList?.any { it.selectStatus } }}
        string('partnerId') {{ DATA_SOURCE.data.merchantVO?.partnerId }}
        number('guestType') {{ DATA_SOURCE.data.checkinGuestVO?.guestType }}
        number('payType') {{ DATA_SOURCE.data.priceVO?.payType }}
        object('defaultGuestInfo') {{
          def guest = DATA_SOURCE?.data?.checkinGuestVO?.guestVOList?.getAt(0)
          guest ? [[ guest ]] : null
        }}
        string('defaultPhoneNum') {{ DATA_SOURCE?.data?.checkinGuestVO?.phone }}
        string('defaultEmail') {{ DATA_SOURCE?.data?.checkinGuestVO?.email }}
      }
      propConfig('prePayInfo') {
        updateBy 'onPrePaymentChange'
        isRequestArg true
      }
      style('style') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
      on('onPrePaymentChange') {
        callMethod('HfeHotelSubmitBottomToolTipBar', 'onGetPaymentInfo')
        transparentArg('', '')
      }
      on('onPrePaymentChange') {
        callMethod('LifecycleLogic', 'prePaymentChange')
        transparentArg('', '')
      }
      on('onPrePaymentChange') {
        callMethod('BottomBar', 'onPreCashierChanged')
        transparentArg('', '')
      }
      on('onScrollTo') {
        callMethod('LayoutTopBottom', 'scrollOffsetY')
        transparentArg('y', 'y')
      }
      on('onTogglePayTip') {
        callMethod('HfeHotelSubmitBottomToolTipBar', 'onTogglePayTip')
        transparentArg('', '')
      }
    }
    node('Invoice', '842') {
      label '酒店提单页-发票'
      xIf {{ !!DATA_SOURCE?.data?.invoiceVO }}
      props {
        object('invoiceInfo') {{ DATA_SOURCE?.data?.invoiceVO }}
        array('poiPhoneList') {{ DATA_SOURCE?.data?.invoiceVO?.poiPhoneList ?: [] }}
        bool('isReschedule') {{ CONST.baseInfo?.isReschedule }}
        string('orderId') {{ CONST.baseInfo?.oldOrderId ?: '-1' }}
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
    }
    node('AfterPayModulesContainer', '748') {
      label '通用模块布局容器组件'
      props {
        number('moduleGap') {{ 0 }}
      }
      style('wrapCardStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
        number('paddingTop') {{ 0 }}
        number('paddingBottom') {{ 0 }}
        number('borderRadius') {{ CONST.Module_BorderRadius }}
      }
      slot('renderModules') {
        node('PreferenceInfo', '723') {
          label '酒店提单-住宿偏好'
          xIf {{ !!DATA_SOURCE?.data?.bookPolicyVO?.specialRequestVO }}
          props {
            object('specialRequestInfo') {{ DATA_SOURCE?.data?.bookPolicyVO?.specialRequestVO }}
            object('preferenceConfigInland') {{
              [
                poiId: DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo?.poiId ?: '-999',
                partnerId: DATA_SOURCE?.data?.merchantVO?.partnerId ?: '-999',
                checkin: DATA_SOURCE?.data?.bookInfoVO?.checkinTimeText ?: CONST.baseInfo?.checkin,
                checkout: DATA_SOURCE?.data?.bookInfoVO?.checkoutTimeText ?: CONST.baseInfo?.checkout,
              ]
            }}
            object('preferenceSelectInfo') {{ PROPS.preferenceSelectInfo ?: null }}
          }
          propConfig('preferenceSelectInfo') {
            updateBy 'onChangePreferenceSelectInfo'
            isRequestArg true
          }
          on('onScrollTo') {
            callMethod('LayoutTopBottom', 'scrollTo')
            transparentArg('', '')
          }
          buildConfig {
            lazyLoad true
          }
        }
        node('PrivacyProtection', '1027') {
          label '酒店提单-隐私保护'
          xIf {{ !!DATA_SOURCE?.data?.bookPolicyVO?.privacyPolicyVO }}
          props {
            object('privacyPolicy') {{ DATA_SOURCE?.data?.bookPolicyVO?.privacyPolicyVO }}
            bool('privacyPolicyCheckStatus') {{ PROPS.privacyPolicyCheckStatus }}
          }
          propConfig('privacyPolicyCheckStatus') {
            updateBy 'onCheckStatusChange'
            isRequestArg true
          }
          buildConfig {
            lazyLoad true
          }
        }
        node('LowerCarbon', '840') {
          label '酒店提单页-低碳环保'
          xIf {{ !!DATA_SOURCE?.data?.bookPolicyVO?.lowerCarbonVO?.title }}
          props {
            bool('isChecked') {{ PROPS.isChecked }}
            object('lowerCarbon') {{ DATA_SOURCE?.data?.bookPolicyVO?.lowerCarbonVO }}
            string('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo.poiId }}
          }
          propConfig('isChecked') {
            updateBy 'onChange'
            isRequestArg true
          }
          buildConfig {
            lazyLoad true
          }
        }
      }
    }
    node('RegisterFlagshipMember', '831') {
      label '酒店提单-旗舰店会员注册'
      xIf {{
        def groupMemberInfo = DATA_SOURCE?.data?.memberVO?.groupMemberVO

        // 境内 & 是旗舰店 & 用户“不是”旗舰店会员
        CONST.baseInfo.isInland && groupMemberInfo?.groupFlagShipGoods && !groupMemberInfo?.groupFlagShipMember
      }}
      props {
        object('groupMemberInfo') {{
          def groupMember = DATA_SOURCE?.data?.memberVO?.groupMemberVO
          if (!groupMember) return null

          return [
           flagshipCouponPackageModuleVO: groupMember.flagshipCouponPackageModuleVO,
           groupFlagShipGoods: groupMember.groupFlagShipGoods,
           groupFlagShipMember: groupMember.groupFlagShipMember,
           loginUrl: groupMember.loginUrl,
           registerGroupMemberInfoVO: groupMember.registerGroupMemberInfoVO,
           registrationRequireInfo: groupMember.registrationRequireInfo,
           realNameAuthInfo: groupMember.realNameAuthInfo,
           groupId: groupMember.groupId
          ]
        }}
        string('memberIdentity') {{ PROPS.memberIdentity }}
        bool('switchValue') {{ CONST.registerFlagshipGroupMember }}
        object('formValue') {{ PROPS.formValue }}
        bool('needMemberAuthenticated') {{ PROPS.needMemberAuthenticated }}
        array('agreementChecked') {{ PROPS.agreementChecked }}
        string('goodsID') {{ CONST.goodsID }}
        string('checkin') {{ CONST.baseInfo.checkin }}
        string('checkout') {{ CONST.baseInfo.checkout }}
        string('partnerId') {{ DATA_SOURCE?.data?.merchantVO?.partnerId }}
        number('guestType') {{ DATA_SOURCE?.data?.checkinGuestVO?.guestType }}
        number('identityNumType') {{ DATA_SOURCE?.data?.bookPolicyVO?.identityNumType }}
      }
      propConfig('switchValue') {
        updateBy 'onSwitchChange'
        isRequestArg true
      }
      propConfig('formValue') {
        updateBy 'onFormChange'
        isRequestArg true
      }
      propConfig('agreementChecked') {
        updateBy 'onAgreementCheckedChange'
        isRequestArg true
      }
      propConfig('memberIdentity') {
        updateBy 'onMemberIdentityChange'
        isRequestArg true
      }
      propConfig('needMemberAuthenticated') {
        updateBy 'onNeedMemberAuthenticatedChange'
        isRequestArg true
      }
      on('onSwitchChange') {
        callMethod('LifecycleLogic', 'update')
      }
      on('onMemberLogin') {
        callMethod('LifecycleLogic', 'update')
      }
      on('onScrollToOffsetY') {
        callMethod('LayoutTopBottom', 'scrollOffsetY')
        transparentArg('y', 'y')
      }
      on('onRefreshData') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('', '')
      }
      buildConfig {
        lazyLoad true
      }
    }
    node('HfeHotelSubmitBuyNotes', '865') {
      label '酒店提单-购买须知'
      props {
        object('welfareMerchant') {{ DATA_SOURCE?.data?.merchantVO?.welfareMerchant }}
        array('bookExplainVO') {{ DATA_SOURCE?.data?.bookPolicyVO?.bookExplainVOList }}
        object('reservePromptInfo') {{ DATA_SOURCE?.data?.bookPolicyVO?.reservePromptInfo }}
        string('cancellation') {{ DATA_SOURCE?.data?.cancelPolicyVO?.cancellation }}
        bool('isHourRoom') {{ CONST.isHourRoom }}
      }
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
    }
    node('LowerService', '1048') {
      label '酒店提单-服务保障'
      xIf {{
        (COMMON_PARAMS.systemInfo.IS_MT || COMMON_PARAMS.systemInfo.IS_HOTEL) && !CONST.baseInfo.isOfflineVIP
      }}
      style('containerStyle') {
        number('marginBottom') {{ CONST.Module_Gap }}
      }
    }
    node('HfeHotelSubmitMoreInfo', '1086') {
      label '酒店提单-更多信息'
      style('containerStyle') {
        number('marginTop') {{ CONST.Module_Gap }}
        number('marginBottom') {{ 48 }}
      }
    }
  }
  slot('renderBottom') {
    node('HfeHotelSubmitBottomToolTipBar', '901') {
      label '酒店提单-底部提示条'
      props {
        bool('hasMMC') {{
          DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule?.couponPackageList?.size() > 0
        }}
        bool('isSelectedMMCouponPackage') {{
          DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule?.couponPackageList?.any { it.selectStatus == true }
        }}
        object('mmBaseInfo') {{
          def maxMMCReducePrice = DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule?.baseShowInfo?.maxCanUseMmcReduceMoneyInAllPackages?.div(100) ?: 0
          def title = DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule?.baseShowInfo?.title?.split('<highlight>')?.getAt(0) ?: '购神券包，本单立减'

          [
            maxMMCReducePrice: maxMMCReducePrice,
            title: title
          ]
        }}
        number('backPrice') {{ DATA_SOURCE.data?.priceVO?.cashBackTotalAmount }}
        number('payPrice') {{ DATA_SOURCE.data?.priceVO?.afterCashBackTotalPayAmount }}
        bool('hasCashBack') {{ DATA_SOURCE.data?.priceVO?.cashBackTotalAmount > 0 }}
        string('currencySymbol') {{ DATA_SOURCE.data?.priceVO?.currencySymbol }}
        bool('isLinkedBookingCashBack') {{
          // 境外返现激励类型
          def actionCashBack = 100010
          // 首单
          def firstOrder = 1
          def taskCardInfo = DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO?.taskCardInfo
          return taskCardInfo?.actionType == actionCashBack && taskCardInfo?.taskOrderStatus == firstOrder
        }}
        number('totalCashBackTasks') {{
          def activityVOList = DATA_SOURCE?.data?.promotionVO?.activityVOList
          return activityVOList?.findAll { it.activityType == 1 }?.size() ?: 0
        }}
        bool('remotePlace') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingTaskVO?.remotePlace }}
        array('newLinkedTaskList') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingTaskVO?.taskCardVOList }}
        string('multiLinkedTaskCombineInfo') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingTaskVO?.multiTaskCombineInfo }}
        bool('selectedLinkedTaskCacheIsValid') {{ CONST.selectedLinkedTaskFromCache?.isValid }}
        array('linkedCheckList') {{ PROPS.linkedCheckList }}
        string('userId') {{ COMMON_PARAMS.userInfo?.userId }}
      }
      propConfig('linkedCheckList') {
        updateBy 'onUpdateLinkedCheckList'
        isRequestArg true
      }
      on('onScrollToMMC') {
        callMethod('MagicalCouponPackage', 'onScrollToSelf')
        transparentArg('', '')
      }
      on('onScrollToPrePay') {
        callMethod('HfeHotelSubmitPrePay', 'onScrollToSelf')
        transparentArg('', '')
      }
      on('onToggleFloatPromo') {
        callMethod('HfeHotelSubmitPrePay', 'onToggleFloatPromo')
        transparentArg('', '')
      }
      on('onUpdate') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('', '')
      }
      on('onToggleLinkedTask') {
        callMethod('InlandMultipleTask', 'onLinkedTaskChange')
        transparentArg('', '')
      }
      on('onScrollToInlandMultipleTask') {
        callMethod('InlandMultipleTask', 'onScrollToSelf')
      }
      on('onMultiDiscountBottomBarChange') {
        callMethod('BottomBar', 'onMultiDiscountBottomBarChange')
        transparentArg('', '')
      }
    }
    node('BottomBar', '798') {
      label '酒店提单-底部提单栏'
      props {
        bool('isOversea') {{ CONST.baseInfo?.isOversea }}
        bool('isReschedule') {{ CONST.baseInfo?.isReschedule }}
        bool('isOfflineVIP') {{ CONST.baseInfo?.isOfflineVIP }}
        number('roomCount') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
        number('nightCount') {{ DATA_SOURCE?.data?.bookInfoVO?.nightCount }}
        string('currencySymbol') {{ '¥' }}
        number('totalPromotionAmount') {{
          def promotionDiscount = DATA_SOURCE?.data?.priceVO?.totalPromotionAmount

          return promotionDiscount
        }}
        number('groupBuyTotalCouponAmount') {{ DATA_SOURCE?.data?.groupBuyProductVO?.groupBuyTotalCouponAmount }}
        string('payPriceZeroText') {{ '¥0' }}
        number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
        number('groupBuyPayMoney') {{ DATA_SOURCE?.data?.priceVO?.groupBuyPayAmount }}
        number('mmCouponPackageAmountCent') {{
          def selectedMagicalCoupon = DATA_SOURCE?.data?.couponPackageVO?.magicalMemberModule?.couponPackageList?.find { it.selectStatus == true }

          return selectedMagicalCoupon?.couponPackageAmountCent ?: 0
        }}
        number('cashCouponMoney') {{
          def selectedCashCouponMoney = DATA_SOURCE?.data?.promotionVO?.cashCouponModuleVO?.cashCouponVOList?.find { it.selectStatus == true }

          return selectedCashCouponMoney?.amount ?: 0
        }}
        bool('hasCashBack') {{ CONST.hasCashBack }}
        number('payType') {{ DATA_SOURCE?.data?.priceVO?.payType }}
        number('isRegularSuperGroupGoods') {{
          DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superGroupGoods && DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superDealReservationType != 1
        }}
        number('roomFeeAmount') {{ DATA_SOURCE?.data?.priceVO?.roomFeeAmount }}
        number('cashRoomFeeAmount') {{ DATA_SOURCE?.data?.priceVO?.cashRoomFeeAmount }}
        string('mmCouponPackageText') {{ '神券包' }}
        array('priceItemList') {{ DATA_SOURCE?.data?.priceVO?.priceItemList }}
        number('rescheduleOrderPaidAmount') {{ DATA_SOURCE?.data?.priceVO?.rescheduleOrderPaidAmount }}
        string('priceNoteList') {{ DATA_SOURCE?.data?.priceVO?.priceNoteList }}
        string('offlineTaxNote') {{ DATA_SOURCE?.data?.priceVO?.offlineTaxNote }}
        bool('isSuperGroupBuy') {{
          def isSuperGroupBuy = DATA_SOURCE?.data?.goodsVO?.superGroupGoodsVO?.superDealReservationType == 1
          return isSuperGroupBuy
        }}
        number('afterCashBackTotalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.afterCashBackTotalPayAmount }}
        number('diffAmount') {{ DATA_SOURCE?.data?.priceVO?.diffAmount }}
        string('priceProtectMessage') {{ DATA_SOURCE?.data?.priceGuaranteeVO?.priceProtectMessage }}
        number('linkedBookingCashBackAmount') {{ DATA_SOURCE?.data?.priceVO?.linkedAmountVO?.cashBackTotalAmount }}
        string('nearestValidTime') {{ DATA_SOURCE?.data?.promotionVO?.promotionTipVO?.nearestValidTime }}
        number('rescheduleTotalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.rescheduleTotalPayAmount }}
        number('poi_id') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: -999 }}
        number('city_id') {{ CONST.baseInfo?.poiCityID ?: -999 }}
        number('mtMemberLevel') {{ DATA_SOURCE?.data?.memberVO?.mtMemberVO?.mtMemberLevel }}
      }
      on('onCreateOrder') {
        callMethod('LifecycleLogic', 'validateAndSubmit')
      }
      on('onPriceDetailClick') {
        callMethod('HfeHotelSubmitPreviewLogic', 'onUpdateDiscountStatus')
        transparentArg('', '')
      }
      on('onTimeEndRefresh') {
        callMethod('LifecycleLogic', 'update')
        transparentArg('', '')
      }
    }
  }
}

node('LifecycleLogic', '830') {
  label '酒店提单页-页面生命周期逻辑'
  props {
    number('bizType') {{ CONST.baseInfo.bizType }}
    string('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo.poiId }}
    string('poiCityId') {{ CONST.baseInfo.poiCityID }}
    string('goodsID') {{ CONST.goodsID }}
    bool('isHourRoom') {{ CONST.isHourRoom }}
    bool('isTourAround') {{ CONST.isTourAround }}
    string('originalGoodsId') {{ CONST.isRoomUpgrade ? PAGE_QUERY.goods_id : '' }}
    number('superDealSceneType') {{ CONST.baseInfo.superDealSceneType }}
    number('superDealApplyId') {{ CONST.baseInfo.superDealApplyId }}
    number('spuExchangeType') {{ DATA_SOURCE.data?.goodsVO?.spuInfoVO?.spuExchangeType }}
    string('multipleBookingTaskName') {{ DATA_SOURCE?.data?.promotionVO?.linkedBookingShowInfoVO?.taskCardInfo?.taskName }}
    number('spuId') {{ CONST.resSpuId }}
    string('ctPoi') {{ CONST.baseInfo.ctPoi }}
    string('queryId') {{ CONST.baseInfo.queryId }}
    string('contentId') {{ CONST.baseInfo.extraMRNParams?.content_id }}
    string('bussiId') {{ CONST.baseInfo.extraMRNParams?.bussi_id }}
    string('moduleId') {{ CONST.baseInfo.extraMRNParams?.module_id }}
    string('allDeductionCodes') {{
      DATA_SOURCE.data?.memberVO?.mtMemberVO?.rightsModuleVO?.floatingRightsInfoVOList?.collect({ rights ->
        return rights.userRightsInfoVOList?.collect({ item -> item.deductionCode })?.join(':')
      })?.join(',')
    }}
    number('adultNum') {{ CONST.baseInfo.adultNum }}
    array('childAge') {{ CONST.baseInfo.childAge }}
    number('roomNum') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount ?: CONST.baseInfo.roomNum }}
    string('checkin') {{ CONST.baseInfo.checkin }}
    string('checkout') {{ CONST.baseInfo.checkout }}
    number('salePrice') {{ DATA_SOURCE.data?.priceVO?.totalPayAmount }}
    number('originalPrice') {{ DATA_SOURCE.data?.priceVO?.roomFeeAmount }}
    number('cashBackAmount') {{ DATA_SOURCE.data?.priceVO?.cashBackTotalAmount }}
    string('userId') {{ COMMON_PARAMS.userInfo?.userId }}
    string('token') {{ COMMON_PARAMS.userInfo?.token }}
    bool('canPreRetainWithBlindBoxDiscount') {{ DATA_SOURCE.data?.extendVO?.canPreRetainWithBlindBoxDiscount }}
    object('retainParams') {{
      [
        blindBoxSource: CONST.baseInfo?.blindBoxSource ?: '4',
        hotelCustomGpsStatus: COMMON_PARAMS.location?.lat && COMMON_PARAMS.location?.lng ? '1' : '0',
        fingerprint: COMMON_PARAMS.fingerprint.fingerprint,
      ]
    }}
    bool('retainWithBlindBoxDiscount') {{ PROPS.retainWithBlindBoxDiscount }}
    string('blindBoxSource') {{ PROPS.blindBoxSource }}
    bool('needZlCheck') {{ DATA_SOURCE.data?.extendVO?.canZlPreCreateOrderCheck }}
    bool('isBuyMMCPackage') {{
      def selectedMagicalPackageCoupon = DATA_SOURCE.data?.couponPackageVO?.magicalMemberModule?.couponPackageList?.find {it -> it.selectStatus}
      return !!selectedMagicalPackageCoupon
    }}
    bool('isUseMMC') {{
      def selectedMagicalCoupon = DATA_SOURCE.data?.promotionVO?.availableMagicalMemberCouponVOList?.find {it -> it.selectedStatus}
      return !!selectedMagicalCoupon
    }}
    bool('isReceiveRedPacketSucceed') {{ CONST.baseInfo.isReceiveRedPacketSucceed }}
    bool('isShowReceiveRedPacketToast') {{
      // 跳链有参数 && 没有会员权益的toast (领取toast优先级低于会员权益toast)
      CONST.baseInfo.isReceiveRedPacketSucceed && !DATA_SOURCE?.data?.memberVO?.mtMemberVO?.rightsModuleVO?.toast
    }}
    object('createOrderPrompt') {{ DATA_SOURCE.data?.promptModuleVO?.createOrderPromptInfoVO }}
    object('retentionPrompt') {{ DATA_SOURCE.data?.promptModuleVO?.retainPromptInfoVO }}
    object('flagship') {{
      def groupMember = DATA_SOURCE.data?.memberVO?.groupMemberVO

      if (!groupMember) return null

      return [
        needCheck: !!groupMember?.createOrderNeedValidateCheckTypes,
        isOpened: CONST.registerFlagshipGroupMember,
        groupFlagShipGoods: groupMember?.groupFlagShipGoods,
        groupFlagShipMember: groupMember?.groupFlagShipMember,
      ]
    }}
    object('failPromotion') {{ PROPS.failPromotion }}
    bool('removeRealNameVoucher') {{ PROPS.removeRealNameVoucher }}
    string('unPayOrderId') {{ PROPS.unPayOrderId }}
    object('bookInfo') {{
      def bookInfo = DATA_SOURCE.data?.bookInfoVO

      if (!bookInfo) return null

      [
        checkinTimeText: bookInfo.checkinTimeText,
        checkinTimeSubText: bookInfo.checkinTimeSubText,
        checkoutTimeText: bookInfo.checkoutTimeText,
        checkoutTimeSubText: bookInfo.checkoutTimeSubText,
        nightCount: bookInfo.nightCount,
      ]
    }}
    string('cancelRuleDesc') {{
      def cancelPolicy = DATA_SOURCE.data?.cancelPolicyVO

      cancelPolicy?.cancelText ?: cancelPolicy?.cancellation
    }}
    objectWithSub('lx') {
      objectWithSub('submitOrderMcOversea') {
        object('valLab') {{
          return [
            Incentive_Label: CONST?.baseInfo?.Incentive_Label ?: 0,
            Incentive_Label_text: CONST?.baseInfo?.Incentive_Label_text?: '',
            have_price_lable: CONST?.baseInfo?.have_price_lable?: 0,
            price_lable_text: CONST?.baseInfo?.price_lable_text?: '',
            combined_type: DATA_SOURCE?.data?.combinationVO?.combineOrderType?: -999,
          ]
        }}
      }
    }
  }
  propConfig('failPromotion') {
    updateBy 'onFailPromotionChange'
    isRequestArg true
  }
  propConfig('removeRealNameVoucher') {
    updateBy 'onRemoveRealNameVoucherChange'
    isRequestArg true
  }
  propConfig('retainWithBlindBoxDiscount') {
    updateBy 'onRetainWithBlindBoxDiscountChange'
    isRequestArg true
  }
  propConfig('unPayOrderId') {
    updateBy 'onUnPayOrderIdChange'
    isRequestArg true
  }
  propConfig('blindBoxSource') {
    updateBy 'onBlindBoxSourceChange'
    isRequestArg true
  }
  on('onRegisterFlagshipMember') {
    callMethod('RegisterFlagshipMember', 'register')
    transparentArg('', '')
  }
  on('onScrollToRegisterFlagship') {
    callMethod('RegisterFlagshipMember', 'scrollToSelf')
  }
}

node('HfeHotelSubmitRoomDetail', '805') {
  label '酒店提单-房型详情'
  xIf {{ !CONST.isError }}
  props {
    object('roomInformation') {{ DATA_SOURCE?.data?.goodsVO?.roomInfoVO?.roomInformationVO }}
    string('spuId') {{ CONST.baseInfo.extraMRNParams?.spuId }}
    string('userId') {{ COMMON_PARAMS?.userInfo?.userId }}
    number('adultNum') {{ CONST.baseInfo.adultNum }}
    array('childAge') {{ CONST.baseInfo.childAge }}
    string('ctPoi') {{ CONST.baseInfo.ctPoi }}
    string('queryId') {{ CONST.baseInfo.queryId }}
    number('roomNum') {{ DATA_SOURCE?.data?.bookInfoVO?.roomCount }}
    bool('fromOffline') {{ CONST.baseInfo?.fromOffline }}
    number('specialChannel') {{ CONST.baseInfo?.specialChannel }}
    number('goodsType') {{ DATA_SOURCE?.data?.goodsVO?.goodsType }}
    number('goodsId') {{ CONST.goodsID }}
    string('poiId') {{ DATA_SOURCE?.data?.merchantVO?.poiId ?: CONST.baseInfo.poiId }}
    string('checkin') {{ CONST.baseInfo.checkin }}
    string('checkout') {{ CONST.baseInfo.checkout }}
    number('ohEntrance') {{ CONST.baseInfo.extraMRNParams?.oh_entrance }}
    number('realRoomId') {{ CONST.baseInfo?.extraMRNParams?.realRoomId }}
    string('newCancelSaleAB') {{ CONST.baseInfo.extraMRNParams?.newCancelSaleAB }}
    string('partnerId') {{ DATA_SOURCE?.data?.merchantVO?.partnerId ?: PAGE_QUERY.partnerId }}
    string('shopuuid') {{
      DATA_SOURCE?.data?.merchantVO?.shopUuid ?: CONST.baseInfo.extraMRNParams?.shopuuid
    }}
  }
  on('onRoomUpgradeConfirm') {
    callMethod('RoomUpgrade', 'toggle')
  }
}
