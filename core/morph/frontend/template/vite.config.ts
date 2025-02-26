import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import { resolve } from "path";
import ViteRestart from "vite-plugin-restart";
import mdx from "@mdx-js/rollup";
import remarkGfm from "remark-gfm";
import rehypeExtractToc from "@stefanprobst/rehype-extract-toc";
import rehypeExtractTocMdxExport from "@stefanprobst/rehype-extract-toc/mdx";
import rehypeSlug from "rehype-slug";

// https://vitejs.dev/config/
export default defineConfig((env) => ({
  plugins: [
    react(),
    {
      enforce: "pre",
      ...mdx({
        remarkPlugins: [remarkGfm],
        rehypePlugins: [
          rehypeSlug,
          rehypeExtractToc,
          rehypeExtractTocMdxExport,
        ],
      }),
    },
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
    cors: true,
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
