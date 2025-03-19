import { Head } from "@morph-data/frontend/components";
import { RootErrorBoundary, Header, TableOfContents } from "./_morph-data-lib";
import {
  usePageMeta,
  MdxComponentsProvider,
  Outlet,
  useRefresh,
  extractComponents,
} from "@morph-data/frontend/components";
import "./index.css";

const uiComponents = extractComponents(
  import.meta.glob("./_components/ui/**/*.tsx", {
    eager: true,
  })
);

const morphComponents = extractComponents(
  import.meta.glob("./_components/*.tsx", {
    eager: true,
  })
);

export default function App() {
  const pageMeta = usePageMeta();

  useRefresh();

  return (
    <RootErrorBoundary>
      <Head key={pageMeta?.pathname}>
        <title>{pageMeta?.title}</title>
        <link head-key="favicon" rel="icon" href="/static/favicon.ico" />
      </Head>
      <MdxComponentsProvider
        components={{ ...uiComponents, ...morphComponents }}
      >
        <div className="morph-page p-4">
          <Header.Root>
            <Header.DropDownMenu />
            {pageMeta && <Header.PageTitle title={pageMeta.title} />}
            <Header.Spacer />
            <Header.MorphLogo />
          </Header.Root>
          <div className="mt-4 p-2">
            <div className="grid gap-4 grid-cols-[1fr_32px] lg:grid-cols-[1fr_180px]">
              <div className="p-2">
                <Outlet />
              </div>
              <div>
                <TableOfContents
                  toc={pageMeta?.tableOfContents}
                  className="sticky top-10 right-10 h-fit"
                />
              </div>
            </div>
          </div>
        </div>
      </MdxComponentsProvider>
    </RootErrorBoundary>
  );
}
