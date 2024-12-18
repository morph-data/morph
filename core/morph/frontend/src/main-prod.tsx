import "vite/modulepreload-polyfill";
import { createRoot } from "react-dom/client";
import { createInertiaApp } from "@inertiajs/react";
import "./index.css";
import React, { StrictMode } from "react";
import { PageSkeleton } from "./page-skeleton.tsx";
import { PageProvider } from "@use-morph/page";
import "@use-morph/page/css";
import { MDXComponents } from "mdx/types";
import { customMDXComponents } from "./custom-mdx-components.tsx";

type MDXProps = {
  children?: React.ReactNode;
  components?: MDXComponents;
};

export type MDXComponent = (props: MDXProps) => JSX.Element;

type PageModule = { default: MDXComponent }; // types MDX default export
type Pages = Record<string, PageModule>;

const pagesGlobBasePath = "./pages";

const pages: Pages = import.meta.glob<true, string, PageModule>(
  "./pages/**/*.mdx",
  { eager: true }
);

const normalizePath = (filePath: string) => {
  const relativePath = filePath
    .replace(pagesGlobBasePath, "")
    .replace(/\.mdx$/, "");
  return relativePath === "/index" ? "/" : relativePath;
};

const routes = Object.entries(pages).map(([filePath, module]) => {
  // Extract the exported title from the MDX file
  const title = (() => {
    if ("title" in module) {
      return String(module.title);
    }
    return "Untitled";
  })();

  return {
    path: normalizePath(filePath),
    title,
  };
});

document.addEventListener("DOMContentLoaded", () => {
  createInertiaApp({
    resolve: (name) => {
      if (name === "404") {
        return import("./error-page.tsx").then((module) => module.ErrorPage);
      }
      const pageModule = pages[`./pages/${name}.mdx`];

      if (!pageModule) {
        throw new Error(`Page not found: ${name}`);
      }

      const Page = pageModule.default;

      const WrappedComponent: React.FC = (props: {
        token?: string;
        baseUrl?: string;
      }) => (
        <PageProvider {...props}>
          <PageSkeleton routes={routes} title={name}>
            <Page components={customMDXComponents} />
          </PageSkeleton>
        </PageProvider>
      );

      return WrappedComponent;
    },
    setup({ el, App, props }) {
      createRoot(el).render(
        <StrictMode>
          <App {...props} />
        </StrictMode>
      );
    },
  }).then(() => {});
});
