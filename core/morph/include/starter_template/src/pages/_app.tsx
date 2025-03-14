import { Head, Toc } from "@morph-data/components";
import { RootErrorBoundary, Header } from "../lib";
import {
  usePageMeta,
  MdxComponentsProvider,
  Outlet,
} from "@morph-data/frontend/components";

export default function App() {
  const pageMeta = usePageMeta();

  return (
    <RootErrorBoundary>
      <Head>
        <title>{pageMeta?.title}</title>
        <link head-key="favicon" rel="icon" href="/static/favicon.ico" />
      </Head>
      <MdxComponentsProvider>
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
                <Toc
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
