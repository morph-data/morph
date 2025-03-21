import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@/pages/_components/ui/hover-card";
import { Button } from "@/pages/_components/ui/button";
import { LucideTableOfContents } from "lucide-react";
import { cn } from "@/pages/_lib/utils";
import { Toc } from "@morph-data/frontend/components";

export interface TocProps {
  toc?: Toc;
  className?: string;
}

export const TableOfContents: React.FC<TocProps> = ({ toc, className }) => {
  if (!toc) {
    return null;
  }

  return (
    <>
      <div className={cn("toc text-sm w-full hidden lg:block", className)}>
        <div className="grid gird-cols-1 gap-2.5 w-full">
          {toc.map((entry) => (
            <Heading key={entry.id} entry={entry} />
          ))}
        </div>
      </div>
      <div className={cn("toc text-sm w-full lg:hidden", className)}>
        <HoverCard openDelay={300}>
          <HoverCardTrigger asChild>
            <Button variant="ghost">
              <LucideTableOfContents />
            </Button>
          </HoverCardTrigger>
          <HoverCardContent className="w-[16rem]">
            <div className="grid gird-cols-1 gap-2.5 w-full">
              {toc.map((entry) => (
                <Heading key={entry.id} entry={entry} />
              ))}
            </div>
          </HoverCardContent>
        </HoverCard>
      </div>
    </>
  );
};

const Heading = ({ entry }: { entry: Toc[number] }) => {
  return (
    <>
      <a
        href={`#${entry.id}`}
        className="inline-block x-underline text-zinc-400 hover:text-zinc-900 font-normal line-clamp-2"
      >
        {entry.value}
      </a>
      {entry.children?.map((child) => (
        <Heading entry={child} />
      ))}
    </>
  );
};
