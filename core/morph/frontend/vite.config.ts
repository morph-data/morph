import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import path, { resolve } from "path";
import ViteRestart from "vite-plugin-restart";
import { PAGES_GLOB_BASE_DIR_PATH_FROM_FRONTEND_ROOT } from "./constants";

import mdx from "@mdx-js/rollup";
import remarkGfm from "remark-gfm";
import rehypePrettyCode from "rehype-pretty-code";

function addImportToMDX(): Plugin {
  return {
    name: "add-import-to-mdx",
    enforce: "pre",
    transform(code, id) {
      // onnly mdx
      if (id.endsWith(".mdx")) {
        if (
          !code.includes(
            "import { variable, value, morphValue, getJsonStore as getJson } from '@use-morph/page'"
          )
        ) {
          // add import
          return {
            code: `import { variable, value, morphValue, getJsonStore as getJson } from '@use-morph/page';\n${code}`,
            map: null,
          };
        }
      }
      return null;
    },
  };
}

/** @type {import('rehype-pretty-code').Options} */
const prettyCodeOptions = { theme: "github-dark" };

// https://vitejs.dev/config/
export default defineConfig((env) => ({
  plugins: [
    react(),
    {
      enforce: "pre",
      ...mdx({
        remarkPlugins: [remarkGfm],
        rehypePlugins: [[rehypePrettyCode, prettyCodeOptions]],
      }),
    },
    addImportToMDX(),
    ViteRestart({
      restart: [PAGES_GLOB_BASE_DIR_PATH_FROM_FRONTEND_ROOT],
    }),
  ],
  base: env.mode === "development" ? "" : "/_vite-static",
  server: {
    host: "0.0.0.0",
    port: 3000,
    open: false,
    watch: {
      usePolling: true,
      disableGlobbing: false,
    },
    origin: env.mode === "development" ? "http://0.0.0.0:3000" : "",
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
      "/main.js": path.resolve(__dirname, "src/main.tsx"),
    },
  },
  build: {
    outDir: resolve("./dist"),
    assetsDir: "assets",
    target: "es2015",
    manifest: "manifest.json",
    rollupOptions: {
      input: {
        main: resolve("./src/main-prod.tsx"),
      },
      output: {
        entryFileNames: `assets/bundle.js`,
      },
    },
  },
}));
