import React from "react";

type ErrorPageProps = React.PropsWithChildren<{
  routes: Array<{ path: string; title: string }>;
}>;

export const ErrorPage: React.FC<ErrorPageProps> = () => {
  return (
    <div className="h-full min-h-[90svh] w-full flex flex-col justify-center items-center gap-3">
      <h1 className="font-bold text-2xl">Page Not Found</h1>
      <p>Oops! The page you're looking for doesn't exist or has been moved.</p>
      <p>Please select an exsiting page from below.</p>
      <div className="h-full w-full flex flex-col justify-center items-center gap-1 py-2 px-4">
        {/* {props.routes.map((route) => (
          <a key={route.path} href={route.path}>
            <Button variant={"link"}>{route.title}</Button>
          </a>
        ))} */}
      </div>
      <h2 className="font-bold text-lg">Trouble shoot</h2>
      <details className="max-w-[720px] w-full p-4 border border-gray-400 rounded-lg cursor-pointer">
        <summary className="">Newly added files are not displayed.</summary>
        <div className="text-sm flex flex-col gap-3 mt-2">
          <p className="font-bold">You need to re-start mdx dev server.</p>
          <ol>
            <li className="mb-2">1. Close preview window on code editor</li>
            <li className="mb-2">
              2. Stop process with putting{" "}
              <code className="text-sm mx-1 px-1 py-0.5 rounded bg-gray-100 border">
                Ctrl + C
              </code>{" "}
              to the terminal
            </li>
            <li className="mb-2">
              3. Open preview window on code editor again
            </li>
          </ol>
        </div>
      </details>
    </div>
  );
};

export default ErrorPage;
