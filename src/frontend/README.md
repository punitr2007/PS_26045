# IP-SAKTI Sahayak — React Frontend (`sahaya`) 🌿💻

The official web frontend for **IP-SAKTI Sahayak (SIH-26045)**, built with **React 18**, **TypeScript**, **Vite**, and **Tailwind CSS**.

---

## 🎨 Visual Design & Architecture

- **Aesthetic**: Deep Forest Green (`#064e3b`), Emerald Accents, Subtle Glassmorphism, and Obsidian Dark Mode surfaces.
- **Typography**: Inter (sans-serif), JetBrains Mono (statutory citations and code).
- **Core Components**:
  - `ChatWorkspace.tsx`: Multi-turn conversational interface with session preservation, citation chips, and inline interactive clarification panels (`ClarificationPanel`).
  - `drawers.tsx`: Slide-over drawers for **Live Statute Reading** and **Formulation Audit** pre-screening (*Likely Blocked*, *Borderline — Needs Evidence*, *Reasonably Viable*).
  - `routes/index.tsx`: Seamless view switching between the Hero Landing View and the interactive `<ChatWorkspace />` with DOM state preservation on back navigation.
  - `lib/sahayak.ts`: Async client layer interfacing with `/api/v1/chat` and `/api/v1/audit`, statutory identifier mapping, and `"unmapped"` sentinel protection.

---

## 🚀 Running the Frontend

### 1. Install Dependencies
```bash
cd code/frontend/sahaya
npm install
```

### 2. Start Vite Development Server
```bash
npm run dev
```

The application will launch on **`http://localhost:5173`**.

---

## 🔄 Backend Proxy Configuration

The Vite dev server is pre-configured with a reverse proxy in `vite.config.ts` to route all `/api/*` calls directly to the FastAPI backend running on port `8001`:

```ts
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
```

---

## 📁 Component Directory Structure

```
src/
├── components/
│   ├── sahayak/
│   │   ├── ChatWorkspace.tsx    # Multi-turn chat workspace & message stream
│   │   ├── drawers.tsx          # Formulation Audit & Statute Reader drawers
│   │   ├── sidebar.tsx          # History and quick-action navigation
│   │   ├── cards.tsx            # Static cards and informational modules
│   │   └── ClarificationPanel   # Inline slot-filling question quick-replies
│   └── ui/                      # Radix UI primitives (dialog, sheet, button, toast)
├── lib/
│   ├── sahayak.ts               # API caller, statute ID inference & types
│   └── utils.ts                 # Tailwind class merging (clsx + twMerge)
└── routes/
    └── index.tsx                # Landing Page + Chat View switcher
```

---

## 🛠️ Build for Production

```bash
npm run build
```
Build output will be generated in `dist/`.
