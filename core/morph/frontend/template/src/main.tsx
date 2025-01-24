import "vite/modulepreload-polyfill";
import { createRoot } from "react-dom/client";
import { createInertiaApp } from "@inertiajs/react";
import React, { StrictMode } from "react";
import { PageSkeleton } from "./page-skeleton.tsx";
import "@morph-data/components/css";
import { MDXComponents } from "mdx/types";
import { customMDXComponents } from "./custom-mdx-components.tsx";
import { AdminPage } from "./admin/AdminPage.tsx";
import { ErrorPage } from "./error-page.tsx";
import { useRefresh } from "@morph-data/components";

type MDXProps = {
  children?: React.ReactNode;
  components?: MDXComponents;
};

export type MDXComponent = (props: MDXProps) => JSX.Element;

type PageModule = { default: MDXComponent }; // types MDX default export
type Pages = Record<string, PageModule>;

const pages: Pages = import.meta.glob<true, string, PageModule>(
  "/../../src/pages/**/*.mdx",
  {
    eager: true,
  }
);

const normalizePath = (filePath: string) => {
  // const relativePath = filePath.replace(/\.mdx$/, "").replace(/^\.\/pages/, "");
  const relativePath = filePath
    .replace(/\.mdx$/, "")
    .replace(/^\.\.\/\.\.\/src\/pages/, "");

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
  createInertiaApp<{ showAdminPage: boolean }>({
    resolve: (name) => {
      const pageModule = pages[`../../src/pages/${name}.mdx`];

      const WrappedComponent: React.FC<{ showAdminPage: boolean }> = ({
        showAdminPage,
      }) => {
        useRefresh();

        return (
          <PageSkeleton
            routes={routes}
            title={name}
            showAdminPage={showAdminPage}
          >
            {name === "morph" ? (
              <AdminPage />
            ) : pageModule ? (
              <pageModule.default components={customMDXComponents} />
            ) : (
              <ErrorPage routes={routes} />
            )}
          </PageSkeleton>
        );
      };

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
