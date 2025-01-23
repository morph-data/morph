import React from "react";

type QueryResult<T> =
  | {
      status: "loading";
    }
  | {
      status: "success";
      data: T;
    }
  | {
      status: "error";
      error: unknown;
    };

export const useQuery = <T>(fetcher: () => T): QueryResult<Awaited<T>> => {
  const [result, setResult] = React.useState<QueryResult<Awaited<T>>>({
    status: "loading",
  });

  React.useEffect(() => {
    const init = async () => {
      try {
        const data = await fetcher();

        setResult({ status: "success", data });
      } catch (error) {
        setResult({ status: "error", error });
      }
    };

    init();
  }, [fetcher]);

  return result;
};
