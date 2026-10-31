export function bindPasswordVisibility(input, button) {
  if (!input || !button) throw new TypeError('password_visibility_elements_required');
  let visible = false;

  const render = () => {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const direction = input.selectionDirection || 'none';
    input.type = visible ? 'text' : 'password';
    button.textContent = visible ? 'Hide' : 'Show';
    button.setAttribute('aria-label', `${visible ? 'Hide' : 'Show'} password`);
    button.setAttribute('aria-pressed', String(visible));
    if (start !== null && end !== null && typeof input.setSelectionRange === 'function') {
      try { input.setSelectionRange(start, end, direction); } catch { /* Unsupported input implementation. */ }
    }
  };

  button.addEventListener('click', () => {
    visible = !visible;
    render();
  });
  render();
  return () => {
    visible = false;
    render();
  };
}
