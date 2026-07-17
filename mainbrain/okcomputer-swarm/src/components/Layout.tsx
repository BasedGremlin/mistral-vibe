import { Link, useLocation } from "react-router";
import { useAuth } from "@/hooks/useAuth";
import {
  Hexagon,
  Search,
  History,
  Users,
  LayoutDashboard,
  LogIn,
  LogOut,
  User,
  Menu,
  X,
} from "lucide-react";
import { useState, useEffect } from "react";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout, isAdmin } = useAuth();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const isActive = (path: string) => location.pathname === path;

  const navLinks = [
    { path: "/", label: "Home", icon: Search },
    { path: "/swarm", label: "Swarm", icon: Hexagon },
    { path: "/agents", label: "Agents", icon: Users },
    { path: "/history", label: "History", icon: History },
    ...(isAdmin ? [{ path: "/admin", label: "Admin", icon: LayoutDashboard }] : []),
  ];

  return (
    <div className="min-h-[100dvh] relative">
      {/* Neural Cascade Background */}
      <div className="neural-cascade" />

      {/* Header */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
          scrolled
            ? "bg-[#050505]/80 backdrop-blur-md border-b border-[#27272a]/50"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="relative w-8 h-8 flex items-center justify-center">
                <Hexagon
                  className="w-7 h-7 text-[#5B21FF] transition-all duration-300 group-hover:text-[#FFD600]"
                  strokeWidth={2}
                />
                <div className="absolute inset-0 bg-[#5B21FF]/20 rounded-full blur-md opacity-60 group-hover:bg-[#FFD600]/20 transition-all duration-300" />
              </div>
              <span className="text-lg font-bold tracking-tight text-[#FAFAFA]">
                Swarm<span className="text-[#FFD600]">OS</span>
              </span>
            </Link>

            {/* Desktop Nav */}
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-300 flex items-center gap-1.5 ${
                    isActive(link.path)
                      ? "text-[#FFD600] bg-[#FFD600]/10"
                      : "text-[#A1A1AA] hover:text-[#FAFAFA] hover:bg-white/5"
                  }`}
                >
                  <link.icon className="w-4 h-4" />
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Auth */}
            <div className="flex items-center gap-3">
              {user ? (
                <div className="flex items-center gap-3">
                  <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
                    <User className="w-3.5 h-3.5 text-[#5B21FF]" />
                    <span className="text-xs font-medium text-[#A1A1AA]">
                      {user.name || "User"}
                    </span>
                    {isAdmin && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#FFD600]/20 text-[#FFD600] font-bold uppercase tracking-wider">
                        Admin
                      </span>
                    )}
                  </div>
                  <button
                    onClick={logout}
                    className="p-2 rounded-lg text-[#A1A1AA] hover:text-[#FAFAFA] hover:bg-white/5 transition-all duration-300"
                    title="Logout"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-[#5B21FF] text-white hover:bg-[#5B21FF]/80 transition-all duration-300 glow-nova"
                >
                  <LogIn className="w-4 h-4" />
                  Sign In
                </Link>
              )}

              {/* Mobile menu toggle */}
              <button
                onClick={() => setMobileOpen(!mobileOpen)}
                className="md:hidden p-2 rounded-lg text-[#A1A1AA] hover:text-[#FAFAFA] hover:bg-white/5 transition-all duration-300"
              >
                {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Nav */}
        {mobileOpen && (
          <div className="md:hidden bg-[#050505]/95 backdrop-blur-md border-t border-[#27272a]/50">
            <div className="px-4 py-3 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 ${
                    isActive(link.path)
                      ? "text-[#FFD600] bg-[#FFD600]/10"
                      : "text-[#A1A1AA] hover:text-[#FAFAFA] hover:bg-white/5"
                  }`}
                >
                  <link.icon className="w-4 h-4" />
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="relative z-10 pt-16">
        {children}
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-[#27272a]/30 py-6">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs font-mono text-[#52525B]">
            SwarmOS v2.0 // Cognitive Architecture
          </p>
          <div className="flex items-center gap-4">
            <span className="text-xs text-[#52525B] hover:text-[#A1A1AA] transition-colors cursor-pointer">
              Terms
            </span>
            <span className="text-xs text-[#52525B] hover:text-[#A1A1AA] transition-colors cursor-pointer">
              Privacy
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
