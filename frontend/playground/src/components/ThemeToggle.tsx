import React, { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';

export type Theme = 'dark' | 'light';

export function getInitialTheme(): Theme {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('pata_theme') as Theme | null;
    if (saved === 'dark' || saved === 'light') return saved;
  }
  return 'dark'; // default to sleek dark mode
}

export const ThemeToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.remove('dark');
      root.classList.add('light');
    }
    localStorage.setItem('pata_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`relative p-2 rounded-xl border transition-all duration-200 flex items-center justify-center ${
        theme === 'dark'
          ? 'bg-slate-900 hover:bg-slate-800 border-slate-700 text-amber-300 hover:text-amber-200 shadow-sm'
          : 'bg-white hover:bg-slate-100 border-slate-300 text-slate-700 hover:text-slate-900 shadow-sm'
      } ${className}`}
      title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      aria-label={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
    >
      {theme === 'dark' ? (
        <Sun className="h-4 w-4 transition-transform duration-200 hover:rotate-45" />
      ) : (
        <Moon className="h-4 w-4 transition-transform duration-200 hover:-rotate-12 text-indigo-600" />
      )}
    </button>
  );
};
