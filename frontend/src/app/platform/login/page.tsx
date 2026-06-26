import { AuthForm } from "@/features/auth/auth-form";

export default function PlatformLoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(15,23,42,0.12),_transparent_30%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] px-4 py-10">
      <div className="w-full max-w-6xl">
        <AuthForm area="platform" />
      </div>
    </main>
  );
}

