# Oran Data Center Web

Next.js 14 App Router frontend for the Oran Data Center mock-first data center experience.

## Stack

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Zustand
- next-themes

## Routes

- `/:lang/datacenter`
- `/:lang/datacenter/xhs`
- `/:lang/datacenter/xhs/search`
- `/:lang/datacenter/xhs/category/:slug`
- `/:lang/datacenter/xhs/brand/:slug`
- `/:lang/datacenter/xhs/note/:noteId`
- `/:lang/login`

## Local Development

```bash
npm install
npm run dev
```

## Environment

Copy `.env.example` to `.env.local` if needed.

- `NEXT_PUBLIC_API_BASE_URL`: backend API base
- `NEXT_PUBLIC_USE_MOCK_DATA`: keep `true` for the current mock-first phase

## Verification

```bash
npm run typecheck
npm run lint
npm run build
```
