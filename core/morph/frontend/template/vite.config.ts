import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import { resolve } from "path";
import ViteRestart from "vite-plugin-restart";

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
        if (!code.includes("import { state } from '@use-morph/components'")) {
          // add import
          return {
            code: `import { state } from '@use-morph/components';\n${code}`,
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
      restart: ["../../src/pages/**/*"],
    }),
  ],
  base: env.mode === "development" ? "" : "/_vite-static",
  server: {
    host: "0.0.0.0",
    open: false,
    watch: {
      usePolling: true,
      disableGlobbing: false,
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: resolve("./dist"),
    assetsDir: "assets",
    target: "es2015",
    manifest: "manifest.json",
    rollupOptions: {
      input: {
        main: resolve("./src/main.tsx"),
      },
      output: {
        entryFileNames: `assets/bundle.js`,
      },
    },
  },
}));
