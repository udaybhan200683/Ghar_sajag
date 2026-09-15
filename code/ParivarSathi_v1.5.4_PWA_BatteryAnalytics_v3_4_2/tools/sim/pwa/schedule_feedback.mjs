export function nextScheduleFeedback(message='', kind='') {
  return { message: String(message || ''), kind: String(kind || '') };
}
