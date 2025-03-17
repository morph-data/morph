import { PropsWithChildren } from "react";
import { ErrorBoundary, FallbackProps } from "react-error-boundary";

function fallbackRender({ error }: FallbackProps) {
  // Call resetErrorBoundary() to reset the error boundary and retry the render.
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre>{error.message}</pre>
    </div>
  );
}

export const RootErrorBoundary = ({ children }: PropsWithChildren) => {
  return (
    <ErrorBoundary fallbackRender={fallbackRender}>{children}</ErrorBoundary>
  );
};
