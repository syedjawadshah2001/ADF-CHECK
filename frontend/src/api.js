export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      credentials: 'same-origin', ...options,
      headers: { 'X-Requested-With': 'ADF-Web', ...options.headers },
    });
  } catch {
    throw new Error('Cannot connect to the server. Check that the Python API is running.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === 'string' ? body.detail : 'Please check your details and try again.';
    const error = new Error(detail);
    error.status = response.status;
    if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('session-expired'));
    throw error;
  }
  if (options.download) return response.blob();
  return response.status === 204 ? null : response.json();
}

export const sendJSON = (data) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });

export async function downloadFile(id, kind) {
  const blob = await api(`/reviews/${id}/download/${kind}`, { download: true });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = kind === 'pdf' ? 'ADF_Validation_Report.pdf' : `${kind}_document.docx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
