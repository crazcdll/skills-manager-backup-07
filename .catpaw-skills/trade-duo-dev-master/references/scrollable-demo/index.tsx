import { createElement, useRef } from '@max/max';
import Button from '@hfe/max-button';
import ScrollView from '@hfe/max-scrollview';
import Text from '@hfe/max-text';
import View from '@hfe/max-view';
import { remStyleSheet, toPx, toRem } from '@max/leez-style-util';
import { getBottomSpace, getSafeAreaMarginTop, getScreenHeight } from '@max/leez-internal-mix-util';
import HotelDynamicSubmitGuestCard from '../src/index';
import type { GuestCardProps, GuestCardRef } from '../src/types';

// 酒店和门票互斥，分别传给独立实例；quantity 比列表多一项以展示待填写入口。
const hotelMockData: GuestCardProps = {
  hotelQuantity: 3,
  hotelTravelerInfo: {
    title: '入住信息',
    tips: '请填写3间房的入住人信息，姓名须与入住证件保持一致',
    label: '房间',
    vistorInfoList: [
      {
        name: '欧阳美美',
        surname: 'OUYANG',
        givenName: 'MEIMEI',
        areaCode: '+86',
        mobile: '138 0000 0001',
        email: 'meimei@example.com',
      },
      {
        name: '李明',
        englishName: 'LI/MING WITH A LONG ENGLISH NAME',
        areaCode: '+852',
        mobile: '6000 0000',
        email: 'a.long.email.address.for.layout.preview@example.com',
      },
    ],
  },
};

const ticketMockData: GuestCardProps = {
  ticketQuantity: 4,
  ticketTravelerInfo: {
    title: '游客信息',
    tips: '景区要求：购买4张票需提供4位游客信息',
    label: '游客',
    vistorInfoList: [
      {
        name: '江一',
        surname: 'JIANG',
        givenName: 'YI',
        areaCode: '+86',
        mobile: '138 0000 0002',
        email: 'jiangyi@example.com',
        credentials: {
          '1007': 'E00000000',
          '9999': 'MOCK-UNKNOWN-TYPE-0001',
        },
        // 类型名缺失时第二项直接展示编码，验证数据源驱动的兜底分支。
        credentialTypes: {
          '1007': '港澳居民来往内地通行证（回乡证）',
        },
      },
      {
        englishName: 'LI/MING',
        areaCode: '+852',
        mobile: '6000 0000',
        email: 'liming@example.com',
        credentials: {},
      },
      // 已回填但联系方式缺失：不渲染空字段行，点击本地校验后展示手机号提示。
      { name: '王小明' },
    ],
  },
};

// 单分组不追加序号；省略标题、提示和 label，验证默认文案与可选字段。
const singleHotelMockData: GuestCardProps = {
  hotelQuantity: 1,
  hotelTravelerInfo: {
    vistorInfoList: [{ englishName: 'ZHANG/SAN' }],
  },
};

const singleTicketMockData: GuestCardProps = {
  ticketQuantity: 1,
  ticketTravelerInfo: {
    title: '游客信息（单人）',
    tips: '',
    vistorInfoList: [{ name: '张三', mobile: '138 0000 0003' }],
  },
};

// duo preview-comp 的 Home 使用默认 Leez NavigationBar（theme.height=44，safeArea='normal'）。
const PREVIEW_NAVIGATION_BAR_HEIGHT = 44;
// 窗口及安全区值为逻辑像素；仅导航内容高度随 Leez 配置缩放，再转回 remStyleSheet 的输入单位。
const previewScrollHeight = Math.max(
  0,
  getScreenHeight('window') - toPx(PREVIEW_NAVIGATION_BAR_HEIGHT)
    - getSafeAreaMarginTop() - getBottomSpace(),
);

const demoStyles = remStyleSheet({
  scroll: {
    height: toRem(previewScrollHeight),
    flexGrow: 0,
    flexShrink: 1,
  },
  container: {
    flexDirection: 'column',
  },
  section: {
    marginTop: 24,
  },
});

export default function Demo() {
  const hotelRef = useRef<GuestCardRef>(null);
  const ticketRef = useRef<GuestCardRef>(null);
  const singleHotelRef = useRef<GuestCardRef>(null);
  const singleTicketRef = useRef<GuestCardRef>(null);

  // 仅调用组件同步校验，不打开真实常旅客弹窗、不发起提单请求。
  const handleValidate = () => {
    hotelRef.current?.__duo__validate();
    ticketRef.current?.__duo__validate();
    singleHotelRef.current?.__duo__validate();
    singleTicketRef.current?.__duo__validate();
  };

  return (
    <ScrollView style={demoStyles.scroll}>
      <View style={demoStyles.container}>
        <Button onPress={handleValidate}>
          <Text>展示本地校验提示</Text>
        </Button>
        <View style={demoStyles.section}>
          <HotelDynamicSubmitGuestCard ref={hotelRef} {...hotelMockData} />
        </View>
        <View style={demoStyles.section}>
          <HotelDynamicSubmitGuestCard ref={ticketRef} {...ticketMockData} />
        </View>
        <View style={demoStyles.section}>
          <HotelDynamicSubmitGuestCard ref={singleHotelRef} {...singleHotelMockData} />
        </View>
        <View style={demoStyles.section}>
          <HotelDynamicSubmitGuestCard ref={singleTicketRef} {...singleTicketMockData} />
        </View>
      </View>
    </ScrollView>
  );
}
