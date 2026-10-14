export function notFound(): never { throw new Error("notFound"); }
export function redirect(): never { throw new Error("redirect"); }
export function usePathname() { return (globalThis as any).__PATH__ ?? "/"; }
export function useRouter() { return { refresh() {} }; }
export function useSearchParams() { return new URLSearchParams(); }
