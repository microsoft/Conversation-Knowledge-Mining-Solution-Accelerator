# Frontend App (Vite + React + TypeScript)

This project is built with [Vite](https://vitejs.dev/), React, and TypeScript.

## Prerequisites

- Node.js >= 20.0.0
- npm

## Available Scripts

In the project directory, you can run:

### `npm run dev`

Runs the app in development mode.\
Open [http://localhost:5173](http://localhost:5173) to view it in the browser.

The page will hot-reload when you make edits.

### `npm run build`

Type-checks with TypeScript and builds the app for production to the `dist` folder.\
The build is optimized and minified for best performance.

### `npm run preview`

Serves the production build locally for testing before deployment.

### `npm test`

Runs the test suite using [Vitest](https://vitest.dev/).

### `npm run test:watch`

Launches the test runner in interactive watch mode.

## Environment Variables

Environment variables are prefixed with `VITE_` and accessed via `import.meta.env`.

See `.env` for local development configuration:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Learn More

- [Vite Documentation](https://vitejs.dev/guide/)
- [React Documentation](https://react.dev/)
- [Vitest Documentation](https://vitest.dev/)
