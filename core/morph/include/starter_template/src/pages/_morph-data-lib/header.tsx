import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/pages/_components/ui/dropdown-menu";
import { Button } from "@/pages/_components/ui/button";
import { usePages, Link } from "@morph-data/frontend/components";
import { PropsWithChildren } from "react";

const Root = ({ children }: PropsWithChildren) => {
  return <div className="flex items-center gap-3">{children}</div>;
};

const DropDownMenu = () => {
  const pages = usePages();

  return (
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
        {pages.map((page) => (
          <Link to={page.pathname} key={page.pathname}>
            <DropdownMenuItem>
              <span className="truncate max-w-full w-full">{page.title}</span>
            </DropdownMenuItem>
          </Link>
        ))}
        {/* {props.showAdminPage && (
          <>
            <DropdownMenuSeparator />
            <Link href="/morph">
              <DropdownMenuItem>Admin Page</DropdownMenuItem>
            </Link>
          </>
        )} */}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const PageTitle = ({ title }: { title: string }) => {
  return <div className="text-sm text-gray-500">{title}</div>;
};

const Spacer = () => <div className="flex-1" />;

const MorphLogo = () => (
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
);

export const Header = {
  Root,
  DropDownMenu,
  PageTitle,
  Spacer,
  MorphLogo,
};
