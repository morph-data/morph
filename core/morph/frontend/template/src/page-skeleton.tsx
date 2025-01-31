import React from "react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  Button,
  DropdownMenuSeparator,
  Toc,
} from "@morph-data/components";
import { ErrorBoundary, FallbackProps } from "react-error-boundary";
import { Link } from "@inertiajs/react";
import { Toc as TocEntries } from "@stefanprobst/rehype-extract-toc";

function fallbackRender({ error }: FallbackProps) {
  // Call resetErrorBoundary() to reset the error boundary and retry the render.
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre>{error.message}</pre>
    </div>
  );
}

type PageSkeletonProps = React.PropsWithChildren<{
  routes: Array<{ path: string; title: string }>;
  title: string;
  showAdminPage: boolean;
  toc?: TocEntries;
}>;

export const PageSkeleton: React.FC<PageSkeletonProps> = (props) => {
  return (
    <ErrorBoundary fallbackRender={fallbackRender}>
      <div className="morph-page p-4">
        <div className="flex items-center gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="lucide lucide-menu"
                >
                  <line x1="4" x2="20" y1="12" y2="12" />
                  <line x1="4" x2="20" y1="6" y2="6" />
                  <line x1="4" x2="20" y1="18" y2="18" />
                </svg>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-60">
              {props.routes.map((route) => (
                <Link href={route.path} key={route.path}>
                  <DropdownMenuItem>
                    <span className="truncate max-w-full w-full">
                      {route.title}
                    </span>
                  </DropdownMenuItem>
                </Link>
              ))}
              {props.showAdminPage && (
                <>
                  <DropdownMenuSeparator />
                  <Link href="/morph">
                    <DropdownMenuItem>Admin Page</DropdownMenuItem>
                  </Link>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          <div className="text-sm text-gray-500">{props.title}</div>
          <div className="flex-1"></div>
          <div className="text-gray-900 tracking-wide">
            Made with
            <a href="https://www.morph-data.io" className="ml-2">
              <img
                src="https://www.morph-data.io/assets/morph_logo.svg"
                alt="Morph"
                className="h-5 inline"
              />
            </a>
          </div>
        </div>
        <div className="mt-4 p-2">
          <div className="grid gap-4 grid-cols-[1fr_32px] lg:grid-cols-[1fr_180px]">
            <div className="p-2">{props.children}</div>
            <div>
              <Toc toc={props.toc} className="sticky top-10 right-10 h-fit" />
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
};
