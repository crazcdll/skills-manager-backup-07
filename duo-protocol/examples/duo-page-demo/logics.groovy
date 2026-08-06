node('DuoLifecycle', '13') {
  label '内置物料-页面生命周期'
  on('preview.onSuccess') {
    callMethod('LifecycleLogic', 'onPreviewSuccess')
    transparentArg('', '')
  }
  on('preview.onSuccess') {
    callMethod('MeishiCommonEventNav', 'setWebDocumentTitle')
    props {
      string('title') {{ DATA_SOURCE?.data?.merchantVO?.poiName }}
    }
  }
  on('preview.onFail') {
    callMethod('LifecycleLogic', 'onPreviewFail')
    transparentArg('', '')
  }
  on('preview.onEngineFail') {
    callMethod('LifecycleLogicStatic', 'onPreviewEngineFail')
  }
}

node('MeishiCommonEventNav', '90') {
  label '导航API'
}
