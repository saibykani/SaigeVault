"use client";

import { LogOut, MonitorSmartphone, UserRound } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession, useSignOut } from "@/lib/api";

export function initials(name: string | null | undefined, email: string): string {
  const source = name?.trim() || email.split("@")[0] || "?";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0]![0]! + parts[1]![0]! : source.slice(0, 2);
  return letters.toUpperCase();
}

export function AccountMenu() {
  const { data: session, isLoading } = useSession();
  const signOut = useSignOut();

  if (isLoading) return <Skeleton className="size-8 rounded-full" />;
  if (!session) {
    return (
      <Button variant="outline" size="sm" asChild className="ml-1">
        <Link href="/login">
          <UserRound />
          <span className="hidden sm:inline">Sign in</span>
        </Link>
      </Button>
    );
  }

  const { user } = session;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Account: ${user.email}`}
          className="ml-1 flex size-8 items-center justify-center overflow-hidden rounded-full bg-accent text-xs font-semibold text-accent-foreground ring-offset-background outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {user.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- remote avatar, no optimisation needed
            <img
              src={user.avatar_url}
              alt=""
              className="size-full object-cover"
              referrerPolicy="no-referrer"
            />
          ) : (
            initials(user.display_name, user.email)
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate text-sm font-medium text-foreground">
            {user.display_name ?? user.email}
          </span>
          <span className="block truncate text-xs">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings#security">
            <MonitorSmartphone />
            Sessions & devices
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => signOut.mutate()} disabled={signOut.isPending}>
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
