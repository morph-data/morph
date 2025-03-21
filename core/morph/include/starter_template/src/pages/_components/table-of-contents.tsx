import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@/pages/_components/ui/hover-card";
import { Card } from "@/pages/_components/ui/card";
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
            <a className="x-underline" href={`#${entry.id}`}>
              <div
                key={entry.id}
                className="text-zinc-400 hover:text-zinc-900 cursor-pointer font-normal decoration-zinc-400 decoration-0 line-clamp-2"
              >
                <span className="">{entry.value}</span>
              </div>
            </a>
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
            <Card>
              <div className="grid gird-cols-1 gap-2.5 w-full">
                {toc.map((entry) => (
                  <a className="x-underline" href={`#${entry.id}`}>
                    <div
                      key={entry.id}
                      className="text-zinc-400 hover:text-zinc-900 cursor-pointer font-normal decoration-zinc-400 decoration-0 line-clamp-2"
                    >
                      {entry.value}
                    </div>
                  </a>
                ))}
              </div>
            </Card>
          </HoverCardContent>
        </HoverCard>
      </div>
    </>
  );
};
