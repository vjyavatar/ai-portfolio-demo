// Preserve old shared research links while keeping the new landing page lightweight.
const params = new URLSearchParams(location.search);
if (params.has('sym') || params.has('ticker') || /^#[A-Za-z0-9.]{2,10}$/.test(location.hash)) {
  location.replace('/research'+location.search+location.hash);
}
