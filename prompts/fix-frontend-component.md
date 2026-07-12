Audit all frontend components under `frontend/src/`. Find every `.tsx` file and check:

1. **Accessibility**: `aria-label` on all icon/emoji-only buttons. `role` + `tabIndex` + `onKeyDown` on clickable non-button elements.
2. **Error handling**: Async calls wrapped in try/catch with visible UI error state (not just console.error).
3. **Empty states**: Empty/null data shows a friendly message instead of blank space.
4. **No dangerouslySetInnerHTML**: Replace with `whitespace-pre-wrap` or safe text rendering.
5. **Key handlers**: Enter/Space on custom interactive elements.
6. **Polling cleanup**: `mountedRef` guard in useEffect cleanup.

Fix every issue found. Verify: `npm run build` from `frontend/` directory.

Return: table of all files checked and fixes applied.
