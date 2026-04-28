import { ElMessageBox } from 'element-plus'

export function confirmAction(message, title = '确认操作', confirmButtonText = '确认') {
  return ElMessageBox.confirm(message, title, {
    customClass: 'aqc-confirm-box',
    modalClass: 'aqc-confirm-overlay',
    confirmButtonText,
    cancelButtonText: '取消',
    zIndex: 110000,
    showClose: false,
    closeOnClickModal: false,
    closeOnPressEscape: false,
    distinguishCancelAndClose: true,
    autofocus: false,
  })
}

export function confirmDestructiveAction(message, title = '删除确认') {
  return confirmAction(message, title, '确认')
}
