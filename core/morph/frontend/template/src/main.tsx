import "vite/modulepreload-polyfill";
import { createRoot } from "react-dom/client";
import { createInertiaApp, Head } from "@inertiajs/react";
import React, { StrictMode, useMemo } from "react";
import { PageSkeleton } from "./page-skeleton.tsx";
import "@morph-data/components/css";
import { MDXComponents } from "mdx/types";
import type { Toc } from "@stefanprobst/rehype-extract-toc";
import { AdminPage } from "./admin/AdminPage.tsx";
import { ErrorPage } from "./error-page.tsx";
import { useRefresh } from "@morph-data/components";
import { mdxComponents } from "./mdx-componens.tsx";

type MDXProps = {
  children?: React.ReactNode;
  components?: MDXComponents;
};

export type MDXComponent = (props: MDXProps) => JSX.Element;

type PageModule = {
  default: MDXComponent;
  title?: string;
  tableOfContents?: Toc;
}; // types MDX default export
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
    if (module.title) {
      return String(module.title);
    }

    if (module.tableOfContents && module.tableOfContents.length > 0) {
      const firstHeading = module.tableOfContents[0];
      if (firstHeading) {
        return firstHeading.value;
      }
    }

    return "Untitled";
  })();

  return {
    path: normalizePath(filePath),
    title,
    toc: module.tableOfContents,
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

        const firstHeading = useMemo(() => {
          if (
            pageModule?.tableOfContents &&
            pageModule.tableOfContents.length > 0
          ) {
            return pageModule.tableOfContents[0];
          }
          return null;
        }, []);

        const title = pageModule?.title || firstHeading?.value || "Untitled";

        return (
          <>
            <Head title={title}>
              <link head-key="favicon" rel="icon" href="/static/favicon.ico" />
            </Head>
            <PageSkeleton
              routes={routes}
              title={title}
              showAdminPage={showAdminPage}
              toc={pageModule?.tableOfContents}
            >
              {name === "morph" ? (
                <AdminPage />
              ) : pageModule ? (
                <pageModule.default components={mdxComponents} />
              ) : (
                <ErrorPage routes={routes} />
              )}
            </PageSkeleton>
          </>
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
