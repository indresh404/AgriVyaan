import React, { useEffect, useRef, useState, useCallback } from 'react';
import { 
  ArrowDown, 
  ArrowUpRight,
  ChevronLeft, 
  ChevronRight, 
  Menu, 
  X, 
  Sparkles,
  CheckCircle2,
  Cpu, 
  Radio, 
  Terminal, 
  Sliders, 
  Smartphone, 
  Activity, 
  FileText, 
  Video, 
  BookOpen, 
  TrendingUp, 
  Droplets, 
  Building2, 
  Handshake, 
  Leaf, 
  Calendar, 
  BarChart3,
  Compass,
  Zap,
  Users
} from 'lucide-react';

interface AboutPageProps {
  onBackToDashboard: () => void;
}

const TOTAL_FRAMES = 299; // frame000.png to frame298.png

// Navigation items
const NAV_SECTIONS = [
  { id: 'section-problem', label: 'Problem' },
  { id: 'section-idea', label: 'Idea' },
  { id: 'section-phases', label: 'How It Works' },
  { id: 'section-technical', label: 'Technical' },
  { id: 'section-methodology', label: 'Methodology' },
  { id: 'section-business', label: 'Business Model' },
  { id: 'section-impact', label: 'Impact' },
  { id: 'section-sdgs', label: 'SDGs' },
  { id: 'section-resources', label: 'Resources' },
  { id: 'section-future', label: 'Future Scope' }
];

// Helper Component for Staggered One-By-One Scroll Animations
const RevealOnScroll: React.FC<{
  children: React.ReactNode;
  delay?: number;
  className?: string;
  direction?: 'up' | 'left' | 'right' | 'scale';
}> = ({ children, delay = 0, className = '', direction = 'up' }) => {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.10, rootMargin: '0px 0px -30px 0px' }
    );

    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, []);

  const getTransformClass = () => {
    if (!isVisible) {
      if (direction === 'up') return 'opacity-0 translate-y-8';
      if (direction === 'left') return 'opacity-0 -translate-x-8';
      if (direction === 'right') return 'opacity-0 translate-x-8';
      return 'opacity-0 scale-95';
    }
    return 'opacity-100 translate-y-0 translate-x-0 scale-100';
  };

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transition-all duration-700 ease-out transform ${getTransformClass()} ${className}`}
    >
      {children}
    </div>
  );
};

export const AboutPage: React.FC<AboutPageProps> = ({ onBackToDashboard }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scrollSectionRef = useRef<HTMLDivElement>(null);
  const hardwareScrollRef = useRef<HTMLDivElement>(null);
  const heroVideoRef = useRef<HTMLVideoElement>(null);
  const heroCardRef = useRef<HTMLDivElement>(null);

  // Direct DOM refs for HUD elements (prevents React re-renders during scroll)
  // Direct DOM ref for HUD progress bar (prevents React re-renders during scroll)
  const progressBarRef = useRef<HTMLDivElement>(null);

  // State
  const [activeSection, setActiveSection] = useState<string>('section-hero');
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [hardwareScrollProgress, setHardwareScrollProgress] = useState<number>(0);
  const [pageScrollPercent, setPageScrollPercent] = useState<number>(0);

  // Drag to scroll state for Hardware showcase
  const isDraggingHardwareRef = useRef<boolean>(false);
  const startXRef = useRef<number>(0);
  const scrollLeftRef = useRef<number>(0);

  // Animation & Frame Caching State
  const imagesArrayRef = useRef<(HTMLImageElement | null)[]>(new Array(TOTAL_FRAMES).fill(null));
  const isLoadedRef = useRef<boolean[]>(new Array(TOTAL_FRAMES).fill(false));
  const targetProgressRef = useRef<number>(0);
  const currentProgressRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);
  const lastDrawnFrameRef = useRef<number>(-1);
  const isNavigatingRef = useRef<boolean>(false);

  // Ensure hero video autoplays smoothly
  useEffect(() => {
    if (heroVideoRef.current) {
      heroVideoRef.current.play().catch(err => {
        console.warn("Autoplay was prevented on hero video:", err);
      });
    }
  }, []);

  // Preload a single frame
  const loadFrame = useCallback((index: number): Promise<HTMLImageElement | null> => {
    if (index < 0 || index >= TOTAL_FRAMES) return Promise.resolve(null);
    if (imagesArrayRef.current[index]) {
      return Promise.resolve(imagesArrayRef.current[index]);
    }

    return new Promise((resolve) => {
      const img = new Image();
      const formatted = String(index).padStart(3, '0');
      img.src = `/assets/about/hero_animation/frame${formatted}.webp`;
      img.onload = () => {
        imagesArrayRef.current[index] = img;
        isLoadedRef.current[index] = true;
        resolve(img);
      };
      img.onerror = () => {
        resolve(null);
      };
    });
  }, []);

  // Draw frame on canvas with aspect ratio preservation on clean white background
  const drawFrame = useCallback((frameIndex: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let imgToDraw = imagesArrayRef.current[frameIndex];
    if (!imgToDraw) {
      for (let offset = 1; offset < 30; offset++) {
        if (frameIndex - offset >= 0 && imagesArrayRef.current[frameIndex - offset]) {
          imgToDraw = imagesArrayRef.current[frameIndex - offset];
          break;
        }
        if (frameIndex + offset < TOTAL_FRAMES && imagesArrayRef.current[frameIndex + offset]) {
          imgToDraw = imagesArrayRef.current[frameIndex + offset];
          break;
        }
      }
    }

    if (!imgToDraw) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clean White Canvas Background
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    const imgAspect = imgToDraw.naturalWidth / imgToDraw.naturalHeight || (16 / 9);
    const canvasAspect = width / height;

    let drawW: number;
    let drawH: number;
    let drawX: number;
    let drawY: number;

    if (canvasAspect > imgAspect) {
      drawH = height;
      drawW = height * imgAspect;
      drawX = (width - drawW) / 2;
      drawY = 0;
    } else {
      drawW = width;
      drawH = width / imgAspect;
      drawX = 0;
      drawY = (height - drawH) / 2;
    }

    ctx.drawImage(imgToDraw, drawX, drawY, drawW, drawH);
  }, []);

  // Handle Canvas Resize
  const handleResize = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = canvas.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      if (lastDrawnFrameRef.current >= 0) {
        drawFrame(lastDrawnFrameRef.current);
      } else {
        drawFrame(0);
      }
    }
  }, [drawFrame]);

  // Phase Info Helper
  // Smooth RAF Scrubber Loop with capped speed so fast scrolls never skip frames
  useEffect(() => {
    let isRunning = true;

    const loop = () => {
      if (!isRunning) return;

      // Smooth step towards targetProgress with capped speed per tick for silky fluid animation
      const diff = targetProgressRef.current - currentProgressRef.current;
      const absDiff = Math.abs(diff);

      if (absDiff < 0.0008) {
        currentProgressRef.current = targetProgressRef.current;
      } else {
        // Balanced, butter-smooth easing:
        // Responsive speed that tracks scroll tightly while keeping every frame transition silky
        const lerpSpeed = 0.16;
        const minStep = 0.003;
        const maxStep = 0.024;
        const calculatedStep = Math.max(minStep, Math.min(absDiff * lerpSpeed, maxStep));
        currentProgressRef.current += Math.sign(diff) * Math.min(absDiff, calculatedStep);
      }

      const progress = Math.max(0, Math.min(1, currentProgressRef.current));
      const frameIndex = Math.min(
        TOTAL_FRAMES - 1,
        Math.max(0, Math.floor(progress * (TOTAL_FRAMES - 1)))
      );

      // Render frame if changed
      if (frameIndex !== lastDrawnFrameRef.current) {
        drawFrame(frameIndex);
        lastDrawnFrameRef.current = frameIndex;

        // Update Minimal Progress Bar Only
        if (progressBarRef.current) {
          progressBarRef.current.style.width = `${(progress * 100).toFixed(1)}%`;
        }
      }

      rafIdRef.current = requestAnimationFrame(loop);
    };

    rafIdRef.current = requestAnimationFrame(loop);

    return () => {
      isRunning = false;
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [drawFrame]);

  // High-Speed Preloader for all 299 frames
  useEffect(() => {
    let isMounted = true;

    const init = async () => {
      // 1. Immediately preload the first 50 frames (0 to 49) upfront.
      // Guarantees zero glitch/freeze when the user enters the section and starts scrolling.
      const initialFrames = Array.from({ length: 50 }, (_, i) => i);
      await Promise.all(initialFrames.map(idx => loadFrame(idx)));

      if (!isMounted) return;
      handleResize();
      drawFrame(0);

      // 2. High-speed concurrent loader for all remaining frames (50 to 298)
      const concurrency = 20;
      const remainingFrames = Array.from({ length: TOTAL_FRAMES - 50 }, (_, i) => i + 50);
      let nextFrameIdx = 0;

      const worker = async () => {
        while (nextFrameIdx < remainingFrames.length && isMounted) {
          const idx = remainingFrames[nextFrameIdx++];
          if (!imagesArrayRef.current[idx]) {
            await loadFrame(idx);
          }
        }
      };

      await Promise.all(Array.from({ length: concurrency }, () => worker()));
    };

    init();
    window.addEventListener('resize', handleResize);

    return () => {
      isMounted = false;
      window.removeEventListener('resize', handleResize);
    };
  }, [loadFrame, handleResize, drawFrame]);

  // Helper to calculate accurate offsetTop relative to the scroll container
  const getContainerOffsetTop = useCallback((el: HTMLElement | null): number => {
    if (!el) return 0;
    let top = 0;
    let current: HTMLElement | null = el;
    const container = containerRef.current;
    while (current && current !== container) {
      top += current.offsetTop;
      current = current.offsetParent as HTMLElement | null;
    }
    return top;
  }, []);

  // Main Page Scroll Handler with Sticky Timeline & Two-Way Boundary Guards
  const handleScroll = () => {
    const container = containerRef.current;
    if (!container) return;

    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight - container.clientHeight;
    const overallProgress = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
    setPageScrollPercent(overallProgress);

    // Parallax depth effect on hero card as bottom sheet rises over it
    if (heroCardRef.current) {
      const heroHeight = container.clientHeight || 800;
      if (scrollTop <= heroHeight) {
        const p = Math.min(1, Math.max(0, scrollTop / heroHeight));
        heroCardRef.current.style.opacity = `${(1 - p * 0.45).toFixed(3)}`;
        heroCardRef.current.style.transform = `translateY(${(p * 50).toFixed(1)}px)`;
      } else {
        heroCardRef.current.style.opacity = '0.55';
      }
    }

    // Timeline Scrubbing & Boundary Safeguards
    const sec = scrollSectionRef.current;
    if (sec) {
      const secTop = getContainerOffsetTop(sec);
      const clientHeight = container.clientHeight;
      const scrollDistance = sec.offsetHeight - clientHeight;

      if (scrollDistance > 0) {
        if (scrollTop < secTop) {
          // Above timeline (in Hero section)
          targetProgressRef.current = 0;
          // Upward boundary guard:
          // If scrolling up out of timeline but reverse animation hasn't finished (progress > 0.02),
          // hold at secTop until drone returns to start frame.
          if (!isNavigatingRef.current && currentProgressRef.current > 0.02 && scrollTop > secTop - 100) {
            container.scrollTop = secTop;
          }
        } else if (scrollTop >= secTop + scrollDistance) {
          // Below timeline (in Problem/Phases sections)
          targetProgressRef.current = 1;
          // Downward boundary guard:
          // If scrolling down past timeline but flight hasn't finished (progress < 0.98),
          // hold at end of timeline until drone completes scan.
          if (!isNavigatingRef.current && currentProgressRef.current < 0.98 && scrollTop < secTop + scrollDistance + 100) {
            container.scrollTop = secTop + scrollDistance;
          }
        } else {
          // Inside timeline: 100% natural, linear mapping of scroll distance to animation frames
          const rawProgress = (scrollTop - secTop) / scrollDistance;
          targetProgressRef.current = Math.max(0, Math.min(1, rawProgress));
        }
      }
    }

    // Active Section Detection
    const sections = ['section-hero', 'section-timeline', ...NAV_SECTIONS.map(s => s.id)];
    for (let i = sections.length - 1; i >= 0; i--) {
      const el = document.getElementById(sections[i]);
      if (el) {
        const top = getContainerOffsetTop(el) - 180;
        if (scrollTop >= top) {
          setActiveSection(sections[i] === 'section-timeline' ? 'section-phases' : sections[i]);
          break;
        }
      }
    }
  };

  const scrollToSection = (sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el && containerRef.current) {
      isNavigatingRef.current = true;
      const top = sectionId === 'section-hero' ? 0 : getContainerOffsetTop(el);
      containerRef.current.scrollTo({ top, behavior: 'smooth' });
      setActiveSection(sectionId);
      setMobileMenuOpen(false);

      // If user directly clicked a section past the timeline, set timeline to complete
      if (sectionId !== 'section-hero' && sectionId !== 'section-timeline') {
        targetProgressRef.current = 1;
        currentProgressRef.current = 1;
      } else if (sectionId === 'section-hero') {
        targetProgressRef.current = 0;
        currentProgressRef.current = 0;
      }

      setTimeout(() => {
        isNavigatingRef.current = false;
      }, 950);
    }
  };

  const handleBookScanClick = () => {
    // Navigate to the operator workspace home page
    window.location.href = '/';
  };

  // Hardware Horizontal Scroll Handlers
  const handleHardwareScroll = () => {
    const el = hardwareScrollRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    if (maxScroll > 0) {
      setHardwareScrollProgress((el.scrollLeft / maxScroll) * 100);
    }
  };

  const scrollHardware = (direction: 'left' | 'right') => {
    const el = hardwareScrollRef.current;
    if (!el) return;
    const scrollAmount = direction === 'left' ? -320 : 320;
    el.scrollBy({ left: scrollAmount, behavior: 'smooth' });
  };

  // Mouse Drag to Scroll for Hardware Showcase
  const handleMouseDownHardware = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = hardwareScrollRef.current;
    if (!el) return;
    isDraggingHardwareRef.current = true;
    startXRef.current = e.pageX - el.offsetLeft;
    scrollLeftRef.current = el.scrollLeft;
  };

  const handleMouseLeaveHardware = () => {
    isDraggingHardwareRef.current = false;
  };

  const handleMouseUpHardware = () => {
    isDraggingHardwareRef.current = false;
  };

  const handleMouseMoveHardware = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDraggingHardwareRef.current) return;
    e.preventDefault();
    const el = hardwareScrollRef.current;
    if (!el) return;
    const x = e.pageX - el.offsetLeft;
    const walk = (x - startXRef.current) * 1.5;
    el.scrollLeft = scrollLeftRef.current - walk;
  };

  // Active milestone calculation for sidebar
  const activeMilestoneIndex = ['section-hero', ...NAV_SECTIONS.map(s => s.id)].indexOf(activeSection);

  return (
    <div 
      ref={containerRef}
      onScroll={handleScroll}
      className="h-screen w-full overflow-y-auto overflow-x-hidden bg-[#F6F7F3] text-[#192118] font-sans selection:bg-[#1E2B1D] selection:text-white relative"
    >
      {/* 1. TOP FLOATING CAPSULE GLASSMORPHIC NAVBAR */}
      <div className="fixed top-4 left-0 right-0 z-50 w-full px-3 sm:px-6 flex justify-center pointer-events-none">
        <header className="pointer-events-auto w-full max-w-7xl bg-white/80 backdrop-blur-2xl border border-white/70 shadow-xl hover:shadow-2xl rounded-full px-4 sm:px-7 py-2.5 flex items-center justify-between transition-all duration-300">
          
          {/* Brand Wordmark (Scrolls to top) */}
          <div 
            onClick={() => scrollToSection('section-hero')}
            className="flex items-center gap-2.5 cursor-pointer select-none group"
          >
            <div className="w-8 h-8 rounded-full bg-[#1E2B1D] text-white flex items-center justify-center font-black text-xs shadow-sm group-hover:scale-105 transition-transform">
              AV
            </div>
            <span className="font-black text-lg sm:text-xl tracking-tight text-[#142314]">
              AgriVyaan
            </span>
          </div>

          {/* Center Navigation Capsule Links */}
          <nav className="hidden lg:flex items-center gap-1 xl:gap-2 text-xs font-bold text-[#4D584B]">
            {NAV_SECTIONS.map((sec) => {
              const isActive = activeSection === sec.id;
              return (
                <button
                  key={sec.id}
                  onClick={() => scrollToSection(sec.id)}
                  className={`px-3 py-1.5 rounded-full transition-all duration-200 cursor-pointer ${
                    isActive 
                      ? 'bg-[#1E2B1D] text-white shadow-xs font-extrabold scale-105' 
                      : 'hover:text-[#1E2B1D] hover:bg-black/5'
                  }`}
                >
                  {sec.label}
                </button>
              );
            })}
          </nav>

          {/* Right Action CTA: "Book a Scan" -> Redirects to GitHub Repository */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={handleBookScanClick}
              className="flex items-center gap-2 px-5 py-2 rounded-full bg-[#1E2B1D] hover:bg-[#2F422D] text-white text-xs sm:text-sm font-extrabold transition-all shadow-md hover:shadow-lg hover:scale-102 active:scale-98 cursor-pointer"
              title="Visit AgriVyaan on GitHub"
            >
              <span>Book a Scan</span>
              <ArrowUpRight size={14} className="stroke-[2.5]" />
            </button>

            {/* Mobile Hamburger Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-full bg-black/5 text-[#192118] hover:bg-black/10 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </header>
      </div>

      {/* Mobile Glassmorphic Menu Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed top-20 left-4 right-4 z-50 bg-white/95 backdrop-blur-2xl border border-white/80 rounded-3xl p-5 shadow-2xl space-y-3 animate-in fade-in slide-in-from-top-4 duration-200">
          <div className="grid grid-cols-2 gap-2 text-xs font-bold">
            {NAV_SECTIONS.map((sec) => (
              <button
                key={sec.id}
                onClick={() => scrollToSection(sec.id)}
                className={`px-3.5 py-2.5 rounded-xl text-left transition-colors ${
                  activeSection === sec.id ? 'bg-[#1E2B1D] text-white font-extrabold' : 'text-[#4D584B] hover:bg-black/5'
                }`}
              >
                {sec.label}
              </button>
            ))}
          </div>
          <div className="pt-2 border-t border-black/5">
            <button
              onClick={handleBookScanClick}
              className="w-full py-3 rounded-full bg-[#1E2B1D] text-white text-center font-bold text-xs flex items-center justify-center gap-2 shadow-md"
            >
              <span>Explore GitHub Repository</span>
              <ArrowUpRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* 2. SIDE SCROLL-POSITION INDICATOR (DYNAMIC NODE PROGRESS RAIL) */}
      <div className="hidden xl:flex fixed right-6 top-1/2 -translate-y-1/2 z-40 flex-col items-center select-none pointer-events-auto">
        <div className="relative flex flex-col items-center gap-3.5 py-3 px-2 bg-white/60 backdrop-blur-xl border border-white/70 rounded-full shadow-lg">
          {/* Vertical Track */}
          <div className="absolute top-4 bottom-4 w-[2px] bg-black/10 rounded-full" />
          
          {/* Scroll progress fill line */}
          <div 
            className="absolute top-4 w-[2px] bg-[#1E2B1D] rounded-full transition-all duration-100"
            style={{ height: `${Math.min(94, Math.max(2, pageScrollPercent))}%` }}
          />

          {/* Section Milestone Nodes */}
          {[{ id: 'section-hero', label: 'Start' }, ...NAV_SECTIONS].map((sec, idx) => {
            const isCurrent = activeSection === sec.id;
            const isReached = idx <= activeMilestoneIndex;

            return (
              <div key={sec.id} className="group relative flex items-center justify-center">
                {/* Tooltip Label on Hover */}
                <div className={`absolute right-7 px-3 py-1 bg-[#1E2B1D] text-white text-[11px] font-bold rounded-lg shadow-xl pointer-events-none whitespace-nowrap z-50 transition-all duration-200 ${
                  isCurrent ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-2 group-hover:opacity-100 group-hover:translate-x-0'
                }`}>
                  <span className="flex items-center gap-1.5">
                    {isReached && !isCurrent && <span className="text-emerald-400 text-[10px]">✓</span>}
                    {sec.label}
                  </span>
                </div>

                {/* Node Button */}
                <button
                  onClick={() => scrollToSection(sec.id)}
                  aria-label={`Scroll to ${sec.label}`}
                  className={`relative z-10 transition-all duration-300 rounded-full cursor-pointer flex items-center justify-center ${
                    isCurrent 
                      ? 'w-4 h-4 bg-[#1E2B1D] ring-4 ring-[#1E2B1D]/25 scale-125' 
                      : isReached
                        ? 'w-2.5 h-2.5 bg-[#1E2B1D] hover:scale-130'
                        : 'w-2 h-2 bg-black/20 hover:bg-black/50 hover:scale-125'
                  }`}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. HERO SECTION (FULL SCREEN LOOPING VIDEO, PROPER FIT IN WEB VIEW, TOP PADDING 0) */}
      <section 
        id="section-hero" 
        className="sticky top-0 w-full h-screen min-h-[600px] flex items-center justify-start overflow-hidden pt-0 px-4 sm:px-8 lg:px-16 z-0 bg-[#0A110A]"
      >
        {/* Fullscreen Background Video Layer */}
        <div className="absolute -inset-1 w-[calc(100%+8px)] h-[calc(100%+8px)] overflow-hidden pointer-events-none z-0 bg-[#0A110A]">
          <video
            ref={heroVideoRef}
            autoPlay
            loop
            muted
            playsInline
            poster="/assets/about/hero_bg.png"
            className="absolute inset-0 w-full h-full object-cover object-center scale-[1.02]"
          >
            <source src="/assets/about/hero_bg.mp4" type="video/mp4" />
          </video>
          {/* Multi-layered cinematic gradient overlays for high text contrast */}
          <div className="absolute inset-0 bg-gradient-to-r from-black/75 via-black/45 to-transparent z-[10]" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/35 z-[10]" />
        </div>

        {/* Hero Content Card - perfectly fitted in web view */}
        <div ref={heroCardRef} className="relative z-10 w-full max-w-7xl mx-auto flex items-center will-change-transform transition-[opacity,transform] duration-75 ease-out">
          <RevealOnScroll direction="scale" delay={0}>
            <div className="max-w-2xl bg-white/90 backdrop-blur-2xl border border-white/80 rounded-3xl p-6 sm:p-9 shadow-xl space-y-8 text-left">

              {/* Main Headline */}
              <div className="space-y-2">
                <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight text-[#142314] leading-none">
                  AgriVyaan
                </h1>

                <h2 className="text-xl sm:text-2xl lg:text-3xl font-extrabold text-[#1E2B1D] leading-snug">
                  Smart Farming, Powered by Edge AI & Drone Intelligence.
                </h2>
              </div>

              <p className="text-sm sm:text-base lg:text-lg text-[#2C3E2A] font-semibold leading-relaxed">
                A low-cost autonomous drone crop inspection system that catches disease and moisture stress early — before they spread.
              </p>

              {/* Highlights Pill Row */}
              <div className="flex flex-wrap items-center gap-2 pt-1 text-xs font-bold text-[#1E2B1D]">
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-black/5 border border-black/5">
                  <Zap size={13} className="text-emerald-700" />
                  <span>Pixhawk Autopilot Grid</span>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-black/5 border border-black/5">
                  <Cpu size={13} className="text-emerald-700" />
                  <span>Dual-Stage Edge AI</span>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-black/5 border border-black/5">
                  <Radio size={13} className="text-emerald-700" />
                  <span>Dialect Voice Advisory</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex flex-wrap items-center gap-3">
                <button
                  onClick={() => scrollToSection('section-timeline')}
                  className="px-6 py-3 rounded-full bg-[#142314] hover:bg-[#253924] text-white text-xs sm:text-sm font-bold transition-all shadow-lg hover:shadow-xl hover:scale-102 flex items-center gap-2.5 cursor-pointer"
                >
                  <span>Explore Interactive Mission</span>
                  <ArrowDown size={15} />
                </button>

                <button
                  onClick={handleBookScanClick}
                  className="px-5 py-3 rounded-full bg-white/80 hover:bg-white text-[#1E2B1D] border border-black/10 text-xs sm:text-sm font-bold transition-all shadow-sm hover:shadow-md flex items-center gap-2 cursor-pointer"
                >
                  <span>Book a Scan</span>
                  <ArrowUpRight size={15} />
                </button>
              </div>
            </div>
          </RevealOnScroll>
        </div>

        {/* Bottom Scroll Cue */}
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-10 select-none pointer-events-auto">
          <button
            onClick={() => scrollToSection('section-timeline')}
            className="group flex items-center gap-2 px-5 py-2.5 rounded-full bg-white/85 hover:bg-white backdrop-blur-xl border border-white/70 shadow-lg text-[#1E2B1D] text-xs font-bold transition-all hover:scale-105 cursor-pointer"
          >
            <span>Scroll to explore mission</span>
            <ArrowDown size={13} className="group-hover:translate-y-0.5 transition-transform animate-bounce text-emerald-800" />
          </button>
        </div>
      </section>

      {/* BOTTOM PART: OVERLAYS ABOVE STICKY HERO (PARALLAX SHEET EFFECT) */}
      <div className="relative z-10 w-full bg-[#F6F7F3] rounded-t-[36px] sm:rounded-t-[48px] shadow-[0_-30px_70px_-15px_rgba(0,0,0,0.5)]">
        {/* 4. DRONE MISSION TIMELINE (FULL SCREEN ANIMATION & CLEAN PROGRESS BAR ONLY) */}
      <section 
        id="section-timeline" 
        ref={scrollSectionRef}
        className="relative w-full h-[300vh] bg-white rounded-t-[36px] sm:rounded-t-[48px] border-b border-black/5"
      >
        <div className="sticky top-0 left-0 w-full h-screen flex items-center justify-center overflow-hidden select-none rounded-t-[36px] sm:rounded-t-[48px]">
          {/* Sleek top sheet pill grab handle */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 pointer-events-none">
            <div className="w-12 h-1.5 rounded-full bg-black/20 backdrop-blur-md shadow-xs" />
          </div>
          {/* Full Viewport Canvas */}
          <canvas
            ref={canvasRef}
            className="w-full h-full block"
          />

          {/* Minimal Progress Bar Only */}
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20 w-full max-w-md sm:max-w-xl px-6 pointer-events-none">
            <div className="w-full h-1.5 sm:h-2 bg-black/10 backdrop-blur-md rounded-full overflow-hidden shadow-xs">
              <div 
                ref={progressBarRef}
                className="h-full bg-gradient-to-r from-[#1E2B1D] via-emerald-600 to-[#1E2B1D] rounded-full transition-none"
                style={{ width: '0%' }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* 5. PROBLEM & SOLUTION (STAGGERED ONE-BY-ONE ENTRANCE) */}
      <section id="section-problem" className="py-16 sm:py-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-stretch">
          {/* Problem Card */}
          <RevealOnScroll direction="left" delay={0}>
            <div className="h-full bg-white/85 backdrop-blur-2xl border border-white/70 rounded-3xl p-8 sm:p-12 shadow-xl flex flex-col justify-between space-y-8 hover:shadow-2xl transition-all">
              <div className="space-y-4">
                <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-red-50 text-red-700 rounded-full border border-red-200 inline-block">
                  The Ground Reality
                </span>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-[#192118] leading-tight">
                  Late Detection Causes Avoidable Crop Loss
                </h2>
                <p className="text-base sm:text-lg text-[#525B50] leading-relaxed">
                  Small and marginal farmers cannot afford expensive drones or private agronomists. By the time crop disease or water stress is visible to the naked eye, it has already spread throughout the field — causing severe yield loss.
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-[#FAFBF8] border border-black/5 space-y-1.5 text-sm sm:text-base text-[#525B50]">
                <div className="font-bold text-[#192118]">Manual Inspection Limitations:</div>
                <p>Ground walking is slow and uneven. Sub-canopy moisture stress remains invisible until damage is irreversible.</p>
              </div>
            </div>
          </RevealOnScroll>

          {/* Solution Card */}
          <div id="section-idea">
            <RevealOnScroll direction="right" delay={180}>
              <div className="h-full bg-white/85 backdrop-blur-2xl border border-white/70 rounded-3xl p-8 sm:p-12 shadow-xl flex flex-col justify-between space-y-8 hover:shadow-2xl transition-all">
                <div className="space-y-4">
                  <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-emerald-50 text-emerald-800 rounded-full border border-emerald-200 inline-block">
                    The AgriVyaan Innovation
                  </span>
                  <h2 className="text-3xl sm:text-4xl font-extrabold text-[#192118] leading-tight">
                    Shared Drone Intelligence As A Service
                  </h2>
                  <p className="text-base sm:text-lg text-[#525B50] leading-relaxed">
                    Farmers never purchase or maintain hardware. Trained operators fly autonomous missions, while our 2-stage AI pipeline verifies findings before anything reaches the farmer.
                  </p>
                </div>

                <div className="p-5 rounded-2xl bg-[#1E2B1D] text-white space-y-2 text-sm sm:text-base shadow-lg">
                  <div className="font-bold text-emerald-300 uppercase tracking-wider text-xs sm:text-sm">Core Operating Law:</div>
                  <p className="font-medium text-white/95 text-base sm:text-lg">“Detect → Verify → Explain → Recommend — never an unverified AI guess to the farmer.”</p>
                </div>
              </div>
            </RevealOnScroll>
          </div>
        </div>
      </section>

      {/* 6. THE 5-PHASE WORKFLOW (STAGGERED ONE-BY-ONE CARDS) */}
      <section id="section-phases" className="py-16 sm:py-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-12">
        <RevealOnScroll direction="up" delay={0}>
          <div className="text-center space-y-3">
            <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-4 py-1.5 bg-[#EBF0E9] text-[#30432E] rounded-full border border-[#d2decf]">
              End-to-End Workflow
            </span>
            <h2 className="text-4xl sm:text-5xl font-black text-[#192118]">
              The 5-Phase Lifecycle
            </h2>
            <p className="text-base sm:text-lg text-[#525B50] max-w-xl mx-auto">
              From field booking to spoken native-language advisory.
            </p>
          </div>
        </RevealOnScroll>

        <div className="space-y-10">
          {[
            {
              step: '01',
              title: 'Phase 01 — Farmer Books a Scan',
              desc: 'The farmer opens the AgriVyaan mobile app, selects their registered field polygon, and requests an inspection for their preferred date. No hardware to buy, no setup — booking a scan is as effortless as ordering a ride.',
              img: '/assets/about/phase_1.png',
              tag: 'Zero Capex for Farmer · Sub-minute Booking · Auto Dispatch'
            },
            {
              step: '02',
              title: 'Phase 02 — Operator Sets Up Autonomous Mission',
              desc: 'The operator marks field boundaries on GIS satellite imagery. AgriVyaan automatically calculates the optimal flight altitude, lawnmower coverage grid, and battery budget envelope — mission planning is entirely parameter-driven.',
              img: '/assets/about/phase_2.png',
              tag: 'Pixhawk 2.4.8 Autopilot · MAVLink Waypoint Generation · Battery Safe Return'
            },
            {
              step: '03',
              title: 'Phase 03 — Drone Scans, Edge AI Detects',
              desc: 'A fast high-altitude survey flags anomalous crop zones via vegetation indices (ExG/VARI). The drone autonomously returns for low-altitude close-up scans, executing quantized YOLO11 models on-device without internet.',
              img: '/assets/about/phase_3.png',
              tag: '2-Stage Coarse-to-Fine Scan · Raspberry Pi Compute · 100% Offline'
            },
            {
              step: '04',
              title: 'Phase 04 — Operator Verifies & Suggests',
              desc: 'The drone lands and transfers diagnostic data. Every flagged finding — severity score, confidence level, GPS coordinates, and raw cropped imagery — is reviewed by the human operator before creating an advisory.',
              img: '/assets/about/phase_4.png',
              tag: 'Human-in-the-Loop Safeguard · Confidence Escalation · Operator Agronomy Input'
            },
            {
              step: '05',
              title: 'Phase 05 — Farmer Gets Full Spoken Report',
              desc: 'The farmer receives a complete, verified report on their phone with a color-coded field map and dosage instructions. An integrated voice assistant narrates the advisory in Marathi, Hindi, or English so literacy is never a barrier.',
              img: '/assets/about/phase_5.png',
              tag: 'Regional Voice Narration · Actionable Treatment Steps · Offline Cached'
            }
          ].map((phase, idx) => (
            <RevealOnScroll key={idx} direction="up" delay={idx * 120}>
              <div className="bg-white/90 backdrop-blur-2xl border border-white/70 rounded-3xl overflow-hidden shadow-xl hover:shadow-2xl transition-all flex flex-col">
                <div className="w-full bg-[#EAECE6] border-b border-black/5 overflow-hidden flex items-center justify-center">
                  <img 
                    src={phase.img} 
                    alt={phase.title}
                    className="w-full h-auto object-contain block"
                  />
                </div>

                <div className="p-6 sm:p-10 lg:p-12 space-y-4">
                  <div className="flex items-center gap-3.5">
                    <span className="text-xs sm:text-sm font-black px-3.5 py-1 rounded-full bg-[#1E2B1D] text-white">
                      PHASE {phase.step}
                    </span>
                    <h3 className="text-2xl sm:text-3xl font-extrabold text-[#141A14]">
                      {phase.title}
                    </h3>
                  </div>

                  <p className="text-base sm:text-lg text-[#525B50] leading-relaxed max-w-4xl">
                    {phase.desc}
                  </p>

                  <div className="pt-4 border-t border-black/5 flex items-center gap-2 text-sm sm:text-base font-bold text-[#1E2B1D]">
                    <CheckCircle2 size={18} />
                    <span>{phase.tag}</span>
                  </div>
                </div>
              </div>
            </RevealOnScroll>
          ))}
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 7. TECHNICAL DETAILS SECTION (CLEAN PURE WHITE BACKGROUND #FFFFFF)         */}
      {/* ========================================================================= */}
      <section id="section-technical" className="w-full bg-white py-20 sm:py-28 border-y border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          
          {/* Section Header */}
          <RevealOnScroll direction="up" delay={0}>
            <div className="space-y-3">
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-black/5 text-[#333333] rounded-full border border-black/10 inline-block">
                Specification & Architecture
              </span>
              <h2 className="text-4xl sm:text-5xl font-black text-[#000000] tracking-tight">
                Technical Details
              </h2>
              <p className="text-base sm:text-lg text-[#666666] max-w-2xl">
                Precision engineering built for field resilience, offline autonomous execution, and deterministic AI explainability.
              </p>
            </div>
          </RevealOnScroll>

          {/* PART 1 — HARDWARE SHOWCASE (HORIZONTAL SCROLL) */}
          <div className="space-y-6">
            <RevealOnScroll direction="up" delay={50}>
              <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div>
                  <h3 className="text-2xl sm:text-3xl font-bold text-[#000000]">
                    The Hardware Behind AgriVyaan
                  </h3>
                  <p className="text-sm sm:text-base text-[#666666] mt-1">
                    Every component chosen for reliability, low cost, and full offline capability.
                  </p>
                </div>

                {/* Scroll controls */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => scrollHardware('left')}
                    className="p-2.5 rounded-full border border-[#E5E5E5] hover:bg-black/5 text-[#333333] transition-colors cursor-pointer"
                    aria-label="Scroll left"
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <button
                    onClick={() => scrollHardware('right')}
                    className="p-2.5 rounded-full border border-[#E5E5E5] hover:bg-black/5 text-[#333333] transition-colors cursor-pointer"
                    aria-label="Scroll right"
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            </RevealOnScroll>

            {/* Horizontally scrollable row with drag & scroll-snap */}
            <div
              ref={hardwareScrollRef}
              onScroll={handleHardwareScroll}
              onMouseDown={handleMouseDownHardware}
              onMouseLeave={handleMouseLeaveHardware}
              onMouseUp={handleMouseUpHardware}
              onMouseMove={handleMouseMoveHardware}
              className="flex items-stretch gap-5 overflow-x-auto pb-6 pt-2 scrollbar-none snap-x snap-mandatory cursor-grab active:cursor-grabbing select-none"
              style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
            >
              {[
                {
                  img: '/assets/about/technical/pixhawk.png',
                  name: 'Pixhawk 2.4.8',
                  line: 'Flight controller running ArduPilot — handles stabilization, navigation, and safety.',
                  isSoftware: false
                },
                {
                  img: '/assets/about/technical/ardu_logo.png',
                  name: 'ArduPilot + Mission Planner',
                  line: 'Autonomous flight firmware and ground-control software for mission planning and monitoring.',
                  isSoftware: true
                },
                {
                  img: '/assets/about/technical/gps_m8n.png',
                  name: 'GPS + Compass (NEO-M8N)',
                  line: 'Provides precise positioning for autonomous waypoint navigation.',
                  isSoftware: false
                },
                {
                  img: '/assets/about/technical/camera.png',
                  name: 'Onboard Camera',
                  line: 'Captures RGB imagery for Stage 1 and Stage 2 inspection.',
                  isSoftware: false
                },
                {
                  img: '/assets/about/technical/rasberry.png',
                  name: 'Raspberry Pi',
                  line: 'Edge-compute unit — runs the entire on-device AI inspection pipeline.',
                  isSoftware: false
                },
                {
                  img: '/assets/about/technical/esp.png',
                  name: 'ESP32',
                  line: 'Microcontroller managing environmental and soil sensor data over BLE.',
                  isSoftware: false
                },
                {
                  img: '/assets/about/technical/temp_humidity.png',
                  name: 'BME280 Sensor',
                  line: 'Measures temperature and humidity at each flagged zone.',
                  isSoftware: false
                },
                {
                  img: '/assets/about/technical/soil_sensor.png',
                  name: 'Soil Moisture Probe',
                  line: 'Ground-validation sensor for water-stress confirmation.',
                  isSoftware: false
                }
              ].map((hw, idx) => (
                <div
                  key={idx}
                  className="flex-shrink-0 w-[250px] sm:w-[270px] snap-start bg-white border border-[#E5E5E5] rounded-[10px] p-5 shadow-xs hover:shadow-md hover:-translate-y-1 transition-all duration-200 flex flex-col justify-between"
                >
                  <div className="space-y-4">
                    <div className={`w-full h-36 rounded-lg flex items-center justify-center p-3 ${
                      hw.isSoftware ? 'bg-amber-50/70 border border-amber-200/50' : 'bg-[#FAFAFA] border border-[#F0F0F0]'
                    }`}>
                      <img
                        src={hw.img}
                        alt={hw.name}
                        className="max-h-full max-w-full object-contain"
                        draggable={false}
                      />
                    </div>

                    <div>
                      {hw.isSoftware && (
                        <span className="text-[10px] font-bold text-amber-800 uppercase tracking-wider bg-amber-100 px-2 py-0.5 rounded-full inline-block mb-1.5">
                          Software / Firmware
                        </span>
                      )}
                      <h4 className="font-bold text-base text-[#000000] leading-snug">
                        {hw.name}
                      </h4>
                      <p className="text-xs text-[#666666] leading-relaxed mt-1.5">
                        {hw.line}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Scroll progress indicator bar */}
            <div className="w-full h-1 bg-[#F0F0F0] rounded-full overflow-hidden">
              <div
                className="h-full bg-[#1E2B1D] rounded-full transition-all duration-100"
                style={{ width: `${Math.max(12, hardwareScrollProgress)}%` }}
              />
            </div>
          </div>

          {/* PART 2 — SOFTWARE STACK (THREE-BOX LAYOUT STAGGERED) */}
          <div className="space-y-10 pt-8 border-t border-black/5">
            <RevealOnScroll direction="up" delay={0}>
              <div className="text-center space-y-2 max-w-2xl mx-auto">
                <h3 className="text-3xl sm:text-4xl font-black text-[#000000]">
                  The Software Stack
                </h3>
                <p className="text-sm sm:text-base text-[#666666]">
                  Three layers working together — on the ground, in the air, and in the farmer's hand.
                </p>
              </div>
            </RevealOnScroll>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
              {/* Box 1: Mobile App */}
              <RevealOnScroll direction="up" delay={0}>
                <div className="h-full bg-white border border-[#E5E5E5] rounded-2xl p-7 shadow-xs relative flex flex-col justify-between overflow-hidden hover:shadow-md transition-all">
                  <div className="absolute top-0 left-0 right-0 h-1.5 bg-amber-500 rounded-t-2xl" />
                  
                  <div className="space-y-5 pt-2">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-xl bg-amber-50 text-amber-700">
                        <Smartphone size={22} />
                      </div>
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-amber-800 block">Layer 01</span>
                        <h4 className="text-xl font-extrabold text-[#000000]">Farmer Mobile App</h4>
                      </div>
                    </div>

                    <ul className="space-y-3 text-sm text-[#333333] pt-2">
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-2 flex-shrink-0" />
                        <span><strong>Flutter + Dart:</strong> Cross-platform high performance app framework</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-2 flex-shrink-0" />
                        <span><strong>Offline-First:</strong> Local SQLite storage & automated cloud background sync</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-2 flex-shrink-0" />
                        <span><strong>Multilingual Voice:</strong> Spoken vernacular advisory (Marathi, Hindi, English)</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-2 flex-shrink-0" />
                        <span><strong>OCR Reader:</strong> Automated Soil Health Card parsing and field profiling</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-2 flex-shrink-0" />
                        <span><strong>Instant Alerts:</strong> Actionable notifications for urgent crop interventions</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </RevealOnScroll>

              {/* Box 2: Edge AI */}
              <RevealOnScroll direction="up" delay={150}>
                <div className="h-full bg-white border border-[#E5E5E5] rounded-2xl p-7 shadow-xs relative flex flex-col justify-between overflow-hidden hover:shadow-md transition-all">
                  <div className="absolute top-0 left-0 right-0 h-1.5 bg-emerald-600 rounded-t-2xl" />

                  <div className="space-y-5 pt-2">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-800">
                        <Cpu size={22} />
                      </div>
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800 block">Layer 02</span>
                        <h4 className="text-xl font-extrabold text-[#000000]">Edge AI Pipeline (On-Drone)</h4>
                      </div>
                    </div>

                    <ul className="space-y-2.5 text-sm text-[#333333] pt-2">
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mt-2 flex-shrink-0" />
                        <span><strong>Raspberry Pi:</strong> On-device standalone companion compute</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mt-2 flex-shrink-0" />
                        <span><strong>Python + OpenCV:</strong> Laplacian blur gating & matrix transformation</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mt-2 flex-shrink-0" />
                        <span><strong>TensorFlow Lite:</strong> INT8 quantized inference engine without cloud lag</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mt-2 flex-shrink-0" />
                        <span><strong>YOLO11n:</strong> Lightweight on-device disease & pest localized detection</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mt-2 flex-shrink-0" />
                        <span><strong>ExG / VARI / HSV:</strong> Deterministic botanical vegetation indices</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mt-2 flex-shrink-0" />
                        <span><strong>DBSCAN + Haversine:</strong> Geotagged cluster grouping & flight budgeting</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 mt-2 flex-shrink-0" />
                        <span><strong>MAVLink v2:</strong> Real-time telemetry communication protocol</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </RevealOnScroll>

              {/* Box 3: Operator Web Platform */}
              <RevealOnScroll direction="up" delay={300}>
                <div className="h-full bg-white border border-[#E5E5E5] rounded-2xl p-7 shadow-xs relative flex flex-col justify-between overflow-hidden hover:shadow-md transition-all">
                  <div className="absolute top-0 left-0 right-0 h-1.5 bg-blue-600 rounded-t-2xl" />

                  <div className="space-y-5 pt-2">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-xl bg-blue-50 text-blue-700">
                        <Terminal size={22} />
                      </div>
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-blue-800 block">Layer 03</span>
                        <h4 className="text-xl font-extrabold text-[#000000]">Operator Web Platform</h4>
                      </div>
                    </div>

                    <ul className="space-y-3 text-sm text-[#333333] pt-2">
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-2 flex-shrink-0" />
                        <span><strong>React + TypeScript:</strong> Robust component-driven frontend architecture</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-2 flex-shrink-0" />
                        <span><strong>Leaflet.js + Turf.js:</strong> GIS satellite polygon mapping & geospatial tools</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-2 flex-shrink-0" />
                        <span><strong>Supabase:</strong> Scalable real-time backend, telemetry stream & auth</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-2 flex-shrink-0" />
                        <span><strong>Flight Dispatch:</strong> Automated grid generator and battery return envelope</span>
                      </li>
                      <li className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-2 flex-shrink-0" />
                        <span><strong>Agronomy Analytics:</strong> Weather API fusion and dosage calculation engine</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </RevealOnScroll>
            </div>
          </div>

          {/* PART 3 — COMPARISON GRAPHS (STAGGERED ONE-BY-ONE) */}
          <div className="space-y-10 pt-8 border-t border-black/5">
            <RevealOnScroll direction="up" delay={0}>
              <div className="space-y-2">
                <h3 className="text-2xl sm:text-3xl font-bold text-[#000000]">
                  Why Two-Stage Scanning Outperforms Legacy Systems
                </h3>
                <p className="text-sm sm:text-base text-[#666666]">
                  Comparing computational footprint, battery endurance, and sensor sensitivity.
                </p>
              </div>
            </RevealOnScroll>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Chart 1 */}
              <RevealOnScroll direction="up" delay={0}>
                <div className="h-full bg-[#FAFAFA] border border-[#E5E5E5] rounded-2xl p-6 space-y-5">
                  <div className="space-y-1">
                    <h4 className="font-bold text-base text-[#000000]">01. Mission Efficiency & Battery</h4>
                    <p className="text-xs text-[#666666]">Time & battery budget per 5-acre field scan</p>
                  </div>

                  <div className="space-y-4 pt-2">
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs font-semibold text-[#333333]">
                        <span>Full-Field High-Res Scan</span>
                        <span className="text-red-700">42 min (3 Batteries)</span>
                      </div>
                      <div className="w-full h-4 bg-[#E5E5E5] rounded-full overflow-hidden">
                        <div className="w-[92%] h-full bg-[#888888] rounded-full" />
                      </div>
                      <p className="text-[11px] text-[#777777]">High battery + massive storage overhead</p>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs font-bold text-[#1E2B1D]">
                        <span>AgriVyaan Two-Stage Scan</span>
                        <span className="text-emerald-700">11 min (1 Battery)</span>
                      </div>
                      <div className="w-full h-4 bg-[#E5E5E5] rounded-full overflow-hidden">
                        <div className="w-[28%] h-full bg-[#1E2B1D] rounded-full" />
                      </div>
                      <p className="text-[11px] text-emerald-800 font-medium">Same detection coverage, 74% battery savings</p>
                    </div>
                  </div>

                  <p className="text-xs text-[#666666] pt-2 border-t border-black/5">
                    Coarse high-altitude anomaly triage (ExG) triggers targeted low-altitude YOLO scans only where required.
                  </p>
                </div>
              </RevealOnScroll>

              {/* Chart 2 */}
              <RevealOnScroll direction="up" delay={150}>
                <div className="h-full bg-[#FAFAFA] border border-[#E5E5E5] rounded-2xl p-6 space-y-4 flex flex-col justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-base text-[#000000]">02. RGB vs NDVI Spectrum</h4>
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full">
                        🗺️ Sensor Roadmap
                      </span>
                    </div>
                    <p className="text-xs text-[#666666]">Prototype sensor baseline vs NIR roadmap upgrade</p>
                  </div>

                  <div className="grid grid-cols-2 gap-3 py-1">
                    <div className="space-y-1.5 text-center">
                      <div className="h-24 rounded-lg overflow-hidden border border-[#E5E5E5] bg-white flex items-center justify-center">
                        <img src="/assets/potato_rgb.png" alt="RGB Crop Sample" className="h-full w-full object-cover" />
                      </div>
                      <span className="text-[11px] font-bold text-[#333333] block">Current: Standard RGB</span>
                    </div>

                    <div className="space-y-1.5 text-center">
                      <div className="h-24 rounded-lg overflow-hidden border border-[#E5E5E5] bg-white flex items-center justify-center">
                        <img src="/assets/potato_ndvi.png" alt="NDVI Crop Sample" className="h-full w-full object-cover" />
                      </div>
                      <span className="text-[11px] font-bold text-emerald-800 block">Future: Calibrated NDVI</span>
                    </div>
                  </div>

                  <p className="text-xs text-[#666666] pt-2 border-t border-black/5">
                    Near-infrared indices reveal sub-canopy chlorophyll degradation before visible symptoms manifest.
                  </p>
                </div>
              </RevealOnScroll>

              {/* Chart 3 */}
              <RevealOnScroll direction="up" delay={300}>
                <div className="h-full bg-[#FAFAFA] border border-[#E5E5E5] rounded-2xl p-6 space-y-5">
                  <div className="space-y-1">
                    <h4 className="font-bold text-base text-[#000000]">03. Pipeline Architecture Footprint</h4>
                    <p className="text-xs text-[#666666]">Explainable statistical rules vs Heavy black-box ML</p>
                  </div>

                  <div className="space-y-3 pt-2">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-900 font-black text-lg flex items-center justify-center">
                        2
                      </div>
                      <div>
                        <div className="text-xs font-bold text-[#000000]">Trained ML Models</div>
                        <div className="text-xs text-[#666666]">YOLO11n (INT8 quantized) + Stage-1 Classifier</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-900 font-black text-lg flex items-center justify-center">
                        10+
                      </div>
                      <div>
                        <div className="text-xs font-bold text-[#000000]">Deterministic Rule Algorithms</div>
                        <div className="text-xs text-[#666666]">Laplacian Blur, ExG, VARI, HSV, Z-score, DBSCAN</div>
                      </div>
                    </div>
                  </div>

                  <p className="text-xs text-[#666666] pt-2 border-t border-black/5">
                    Deterministic botanical mathematics guarantee transparent reasoning that agronomists can verify.
                  </p>
                </div>
              </RevealOnScroll>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 8. DEVELOPMENT METHODOLOGY / IMPLEMENTATION PHASES (STAGGERED)            */}
      {/* ========================================================================= */}
      <section id="section-methodology" className="w-full bg-[#FFFFFF] py-20 sm:py-28 border-b border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          <RevealOnScroll direction="up" delay={0}>
            <div className="text-center space-y-3 max-w-3xl mx-auto">
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-black/5 text-[#333333] rounded-full border border-black/10 inline-block">
                Engineering Rigor
              </span>
              <h2 className="text-4xl sm:text-5xl font-black text-[#000000] tracking-tight">
                How We Built It — Development Methodology
              </h2>
              <p className="text-base sm:text-lg text-[#666666]">
                A staged build order — each layer proven in hardware and field simulation before the next was added.
              </p>
            </div>
          </RevealOnScroll>

          {/* Staged Milestone Grid with Staggered Entrance */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                stage: 'Stage 01',
                title: 'Autonomous Flight First',
                icon: <Radio size={20} className="text-emerald-700" />,
                desc: 'Before any AI or sensors, we proved the drone could fly a pre-planned mission autonomously — Pixhawk + ArduPilot handling takeoff, waypoint navigation, and safe return-to-launch with MAVLink.',
                status: '✅ Validated',
                statusColor: 'bg-emerald-50 text-emerald-800 border-emerald-200'
              },
              {
                stage: 'Stage 02',
                title: 'Sensor Integration',
                icon: <Activity size={20} className="text-emerald-700" />,
                desc: 'Once flight was reliable, we added the ESP32 + BME280 (temperature/humidity) and the soil-moisture probe, verifying sensor readings could be reliably tagged with GPS position and timestamp mid-mission.',
                status: '✅ Validated',
                statusColor: 'bg-emerald-50 text-emerald-800 border-emerald-200'
              },
              {
                stage: 'Stage 03',
                title: 'Edge AI Pipeline (Formula Layer)',
                icon: <Zap size={20} className="text-emerald-700" />,
                desc: 'We built the deterministic layer first — blur detection, vegetation indices (ExG/VARI), HSV classification, and Z-score anomaly scoring — proving the system could flag suspicious zones without a model.',
                status: '✅ Validated',
                statusColor: 'bg-emerald-50 text-emerald-800 border-emerald-200'
              },
              {
                stage: 'Stage 04',
                title: 'Trained Model Integration (YOLO11n)',
                icon: <Cpu size={20} className="text-amber-700" />,
                desc: 'With the formula layer proven, we layered in the two trained ML components — the optional Stage-1 classifier and the Stage-2 YOLO11n disease/pest detector — quantized to INT8 for on-device inference.',
                status: '🧪 In Progress — Fine-Tuning',
                statusColor: 'bg-amber-50 text-amber-800 border-amber-200'
              },
              {
                stage: 'Stage 05',
                title: 'Two-Stage Mission Logic',
                icon: <Sliders size={20} className="text-emerald-700" />,
                desc: 'Clustering (DBSCAN + Haversine), priority ranking, and battery-budgeted cluster selection were integrated to connect Stage 1 findings to Stage 2 targeted rescan in one coherent mission.',
                status: '✅ Validated',
                statusColor: 'bg-emerald-50 text-emerald-800 border-emerald-200'
              },
              {
                stage: 'Stage 06',
                title: 'Operator Application',
                icon: <Terminal size={20} className="text-emerald-700" />,
                desc: 'Booking, mission planning, live flight monitoring, and human verification workflows were built to give certified operators control and review authority over every finding.',
                status: '✅ Validated',
                statusColor: 'bg-emerald-50 text-emerald-800 border-emerald-200'
              },
              {
                stage: 'Stage 07',
                title: 'Farmer App & Voice Layer',
                icon: <Smartphone size={20} className="text-emerald-700" />,
                desc: 'The offline-first farmer app, report visualization, and native-language voice assistant were built to convert verified technical findings into spoken advice in regional dialects.',
                status: '✅ Validated',
                statusColor: 'bg-emerald-50 text-emerald-800 border-emerald-200'
              },
              {
                stage: 'Stage 08',
                title: 'Closed-Loop Tracking',
                icon: <TrendingUp size={20} className="text-blue-700" />,
                desc: 'Action tracking, before/after comparison, and harvest-outcome recording close the loop — turning the system from a one-time detector into a season-long decision-support tool.',
                status: '🗺️ Roadmap — Data Collection',
                statusColor: 'bg-blue-50 text-blue-800 border-blue-200'
              }
            ].map((stg, idx) => (
              <RevealOnScroll key={idx} direction="up" delay={(idx % 4) * 100}>
                <div className="h-full bg-white border border-[#E5E5E5] rounded-2xl p-6 shadow-xs flex flex-col justify-between space-y-4 hover:border-black/20 hover:shadow-md transition-all">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-extrabold text-[#999999] tracking-wider uppercase">
                        {stg.stage}
                      </span>
                      <div className="p-2 bg-[#F6F7F3] rounded-lg">
                        {stg.icon}
                      </div>
                    </div>

                    <h4 className="font-extrabold text-lg text-[#000000] leading-snug">
                      {stg.title}
                    </h4>

                    <p className="text-xs sm:text-sm text-[#666666] leading-relaxed">
                      {stg.desc}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-[#F0F0F0]">
                    <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full border inline-block ${stg.statusColor}`}>
                      {stg.status}
                    </span>
                  </div>
                </div>
              </RevealOnScroll>
            ))}
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 9. BUSINESS MODEL SECTION (STAGGERED)                                     */}
      {/* ========================================================================= */}
      <section id="section-business" className="w-full bg-[#FAFAFA] py-20 sm:py-28 border-b border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          <RevealOnScroll direction="up" delay={0}>
            <div className="text-center space-y-3 max-w-2xl mx-auto">
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-black/5 text-[#333333] rounded-full border border-black/10 inline-block">
                Sustainable Economics
              </span>
              <h2 className="text-4xl sm:text-5xl font-black text-[#000000] tracking-tight">
                How It Reaches Farmers
              </h2>
              <p className="text-base sm:text-lg text-[#666666]">
                A shared-service model built to remove the cost barrier, not add one.
              </p>
            </div>
          </RevealOnScroll>

          {/* 4 Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                icon: <Calendar size={24} />,
                color: 'bg-emerald-50 text-emerald-800',
                title: 'Pay-Per-Scan',
                desc: 'Individual farmers pay a minimal fee per scan for a fixed acreage — zero equipment purchase, maintenance, or licensing overhead.'
              },
              {
                icon: <Handshake size={24} />,
                color: 'bg-blue-50 text-blue-800',
                title: 'Large Farm Contracts',
                desc: 'Commercial agricultural estates and farmer cooperatives subscribe to recurring weekly or monthly flight schedules across hundreds of acres.'
              },
              {
                icon: <BarChart3 size={24} />,
                color: 'bg-purple-50 text-purple-800',
                title: 'Premium Analytics',
                desc: 'Aggregated historical crop yield trends, zone-wise moisture variance heatmaps, and AI harvest risk forecasts via annual subscription.'
              },
              {
                icon: <Building2 size={24} />,
                color: 'bg-amber-50 text-amber-800',
                title: 'Govt Partnerships',
                desc: 'Subsidized cluster deployment via agricultural extension departments and state crop damage insurance appraisal programs.'
              }
            ].map((card, idx) => (
              <RevealOnScroll key={idx} direction="up" delay={idx * 100}>
                <div className="h-full bg-white border border-[#E5E5E5] rounded-2xl p-7 shadow-xs hover:shadow-md transition-all space-y-3">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${card.color}`}>
                    {card.icon}
                  </div>
                  <h4 className="font-bold text-xl text-[#000000]">{card.title}</h4>
                  <p className="text-sm text-[#666666] leading-relaxed">{card.desc}</p>
                </div>
              </RevealOnScroll>
            ))}
          </div>

          {/* Shared Cluster Diagram */}
          <RevealOnScroll direction="scale" delay={200}>
            <div className="bg-white border border-[#E5E5E5] rounded-3xl p-8 sm:p-12 shadow-sm text-center max-w-4xl mx-auto space-y-6">
              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#1E2B1D]/5 text-[#1E2B1D] text-xs font-bold">
                <Users size={14} />
                Cluster Sharing Topology
              </div>

              <h3 className="text-2xl sm:text-3xl font-extrabold text-[#000000]">
                One Operator — Shared Across a Cluster of Villages
              </h3>

              <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-8 py-6 border-y border-[#F0F0F0]">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-16 h-16 rounded-2xl bg-[#1E2B1D] text-white flex items-center justify-center shadow-md">
                    <Compass size={32} />
                  </div>
                  <span className="text-xs font-bold text-[#192118]">1 Certified Operator</span>
                </div>

                <div className="text-2xl text-black/20 font-bold hidden sm:block">➔</div>

                <div className="flex flex-wrap items-center justify-center gap-3">
                  {['Village A (20 Fields)', 'Village B (35 Fields)', 'Village C (28 Fields)', 'Village D (18 Fields)'].map((v, i) => (
                    <div key={i} className="px-4 py-2.5 rounded-xl bg-[#F6F7F3] border border-black/5 text-xs font-semibold text-[#333333]">
                      🌾 {v}
                    </div>
                  ))}
                </div>
              </div>

              <p className="text-sm text-[#666666] max-w-2xl mx-auto">
                Drones and operators are shared like existing tractor and harvester rental models — keeping diagnostic costs as low as a few rupees per acre even for the smallest landholding.
              </p>
            </div>
          </RevealOnScroll>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 10. IMPACT SECTION WITH GRAPHS (STAGGERED)                                */}
      {/* ========================================================================= */}
      <section id="section-impact" className="w-full bg-white py-20 sm:py-28 border-b border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          <RevealOnScroll direction="up" delay={0}>
            <div className="text-center space-y-3 max-w-2xl mx-auto">
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-emerald-50 text-emerald-800 rounded-full border border-emerald-200 inline-block">
                Measurable Outcomes
              </span>
              <h2 className="text-4xl sm:text-5xl font-black text-[#000000] tracking-tight">
                The Expected Impact
              </h2>
              <p className="text-base sm:text-lg text-[#666666]">
                Outcomes this design is built to enable — framed as design targets.
              </p>
            </div>
          </RevealOnScroll>

          {/* 5 Impact Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: <Sparkles size={20} />,
                color: 'bg-emerald-100 text-emerald-800',
                title: 'Earlier Detection',
                desc: 'Zone-level anomaly flagging catches fungal blights and water stress days before symptoms become visible across the canopy.'
              },
              {
                icon: <Droplets size={20} />,
                color: 'bg-blue-100 text-blue-800',
                title: 'Reduced Blanket Spraying',
                desc: 'GPS-tagged, zone-specific treatment maps replace indiscriminate field-wide chemical spraying, cutting farmer input costs.'
              },
              {
                icon: <Leaf size={20} />,
                color: 'bg-amber-100 text-amber-800',
                title: 'Water Efficiency',
                desc: 'Integration with ground soil-moisture probes prevents both moisture deficit stress and wasteful over-irrigation.'
              },
              {
                icon: <Users size={20} />,
                color: 'bg-purple-100 text-purple-800',
                title: 'Precision Ag for Smallholders',
                desc: 'Shared service model eliminates the $5,000+ commercial drone ownership barrier, democratizing smart agriculture.'
              },
              {
                icon: <TrendingUp size={20} />,
                color: 'bg-emerald-100 text-emerald-800',
                title: 'Closed-Loop Outcome Tracking',
                desc: 'Continuous seasonal recording provides verifiable ROI feedback to the farmer and builds regional agronomy dataset records over time.',
                span: 'sm:col-span-2 lg:col-span-2'
              }
            ].map((imp, idx) => (
              <RevealOnScroll key={idx} direction="up" delay={idx * 100} className={imp.span || ''}>
                <div className="h-full bg-[#FAFAFA] border border-[#E5E5E5] rounded-2xl p-6 space-y-3 hover:shadow-md transition-all">
                  <div className={`p-3 rounded-xl w-fit ${imp.color}`}>
                    {imp.icon}
                  </div>
                  <h4 className="font-bold text-lg text-[#000000]">{imp.title}</h4>
                  <p className="text-xs sm:text-sm text-[#666666] leading-relaxed">{imp.desc}</p>
                </div>
              </RevealOnScroll>
            ))}
          </div>

          {/* Conceptual Risk Reduction Visual Model */}
          <RevealOnScroll direction="scale" delay={150}>
            <div className="bg-[#FAFBF8] border border-[#E5E5E5] rounded-3xl p-8 sm:p-12 shadow-sm space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h4 className="text-xl font-bold text-[#000000]">
                    Conceptual Yield-Risk Reduction Over a Growing Season
                  </h4>
                  <p className="text-xs sm:text-sm text-[#666666]">
                    Simulated disease escalation trajectory comparing unmonitored vs early-intervention crops.
                  </p>
                </div>
                <div className="flex items-center gap-4 text-xs font-bold">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-red-500" />
                    <span>Without Early Detection</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-emerald-600" />
                    <span>With AgriVyaan Monitoring</span>
                  </div>
                </div>
              </div>

              {/* SVG Trajectory Chart */}
              <div className="w-full h-48 bg-white border border-[#E5E5E5] rounded-2xl p-4 flex items-center justify-center">
                <svg className="w-full h-full" viewBox="0 0 600 150" fill="none">
                  <line x1="40" y1="20" x2="580" y2="20" stroke="#F0F0F0" strokeWidth="1" />
                  <line x1="40" y1="60" x2="580" y2="60" stroke="#F0F0F0" strokeWidth="1" />
                  <line x1="40" y1="100" x2="580" y2="100" stroke="#F0F0F0" strokeWidth="1" />
                  <line x1="40" y1="130" x2="580" y2="130" stroke="#CCCCCC" strokeWidth="1.5" />

                  {/* Unmonitored Path */}
                  <path
                    d="M 40 120 Q 200 115, 300 80 T 580 25"
                    fill="none"
                    stroke="#EF4444"
                    strokeWidth="3"
                    strokeDasharray="6 3"
                  />

                  {/* AgriVyaan Protected Path */}
                  <path
                    d="M 40 120 Q 180 110, 260 115 T 400 120 T 580 125"
                    fill="none"
                    stroke="#10B981"
                    strokeWidth="3.5"
                  />

                  <circle cx="260" cy="115" r="5" fill="#10B981" stroke="#FFFFFF" strokeWidth="2" />
                  <text x="270" y="110" fontSize="10" fill="#047857" fontWeight="bold">Day 22: Target Spot Sprayed</text>
                </svg>
              </div>

              <p className="text-xs text-[#777777] italic text-center">
                *Illustrative model, not measured field results — validation against real harvest data is part of the roadmap (see Methodology, Stage 8).
              </p>
            </div>
          </RevealOnScroll>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 11. SUSTAINABLE DEVELOPMENT GOALS (SDG) (STAGGERED)                       */}
      {/* ========================================================================= */}
      <section id="section-sdgs" className="w-full bg-[#FFFFFF] py-20 sm:py-28 border-b border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          <RevealOnScroll direction="up" delay={0}>
            <div className="text-center space-y-3 max-w-2xl mx-auto">
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-blue-50 text-blue-800 rounded-full border border-blue-200 inline-block">
                Global Alignment
              </span>
              <h2 className="text-4xl sm:text-5xl font-black text-[#000000] tracking-tight">
                Sustainable Development Goals
              </h2>
              <p className="text-base sm:text-lg text-[#666666]">
                AgriVyaan's design maps directly to five United Nations SDGs.
              </p>
            </div>
          </RevealOnScroll>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
            {[
              {
                img: '/assets/about/sdg1.jpeg',
                title: 'SDG 1 — No Poverty',
                desc: 'Protects farmer income by catching crop damage early and removing the hardware-ownership cost barrier.'
              },
              {
                img: '/assets/about/sdg2.jpeg',
                title: 'SDG 2 — Zero Hunger',
                desc: 'Improves crop health monitoring and early intervention, supporting more reliable food production.'
              },
              {
                img: '/assets/about/sdg9.jpeg',
                title: 'SDG 9 — Industry & Innovation',
                desc: 'Brings edge-AI drone monitoring to smallholders through an affordable, shared-access model.'
              },
              {
                img: '/assets/about/sdg12.jpeg',
                title: 'SDG 12 — Responsible Production',
                desc: 'Zone-specific recommendations replace blanket pesticide and chemical fertilizer application.'
              },
              {
                img: '/assets/about/sdg13.jpeg',
                title: 'SDG 13 — Climate Action',
                desc: 'Environmental risk flags (heat, drought, flood) help farmers adapt to changing micro-climates.'
              }
            ].map((sdg, idx) => (
              <RevealOnScroll key={idx} direction="up" delay={idx * 90}>
                <div className="h-full bg-white border border-[#E5E5E5] rounded-2xl p-5 shadow-xs hover:shadow-md hover:-translate-y-1 transition-all flex flex-col justify-between space-y-4">
                  <div className="space-y-4">
                    <div className="w-full aspect-square rounded-xl overflow-hidden bg-[#FAFAFA] border border-[#F0F0F0] flex items-center justify-center">
                      <img
                        src={sdg.img}
                        alt={sdg.title}
                        className="w-full h-full object-contain"
                      />
                    </div>

                    <div>
                      <h4 className="font-extrabold text-base text-[#000000] leading-snug">
                        {sdg.title}
                      </h4>
                      <p className="text-xs text-[#666666] leading-relaxed mt-2">
                        {sdg.desc}
                      </p>
                    </div>
                  </div>
                </div>
              </RevealOnScroll>
            ))}
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 12. PROJECT RESOURCES SECTION (STAGGERED)                                 */}
      {/* ========================================================================= */}
      <section id="section-resources" className="w-full bg-[#FAFAFA] py-20 sm:py-28 border-b border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          <RevealOnScroll direction="up" delay={0}>
            <div className="text-center space-y-3 max-w-2xl mx-auto">
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider px-3.5 py-1 bg-black/5 text-[#333333] rounded-full border border-black/10 inline-block">
                Open Knowledge Base
              </span>
              <h2 className="text-4xl sm:text-5xl font-black text-[#000000] tracking-tight">
                Project Resources
              </h2>
              <p className="text-base sm:text-lg text-[#666666]">
                Everything about AgriVyaan — documentation, live demo, source code, and scientific research.
              </p>
            </div>
          </RevealOnScroll>

          {/* PART A: Quick Action Links Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-5">
            {[
              {
                title: 'Pitch Deck (PPT)',
                sub: 'View the presentation',
                icon: <FileText size={22} className="text-amber-700" />,
                url: 'https://docs.google.com/presentation/d/1GaS0Wj-AfxVvHpPIqzMU1IhMtrjGkWKB/edit?usp=sharing&ouid=117158046606615056376&rtpof=true&sd=true'
              },
              {
                title: 'Demo Pitch (YouTube)',
                sub: 'Watch the walkthrough',
                icon: <Video size={22} className="text-red-700" />,
                url: 'https://www.youtube.com/watch?v=wwioPaxjWgg'
              },
              {
                title: 'GitHub Repository',
                sub: 'Explore the source code',
                icon: <Terminal size={22} className="text-black" />,
                url: 'https://github.com/indresh404/Agri-Vyaan'
              },
              {
                title: 'Notion Docs',
                sub: 'Full project notes',
                icon: <BookOpen size={22} className="text-blue-700" />,
                url: 'https://www.notion.so/Agri-Vyaan-3e1a2c1b3dd180e68ffcd746a33d5ec6?source=copy_link'
              },
              {
                title: 'Technical Reports',
                sub: 'Detailed tech docs (Drive)',
                icon: <FolderGit2Custom size={22} className="text-emerald-700" />,
                url: 'https://drive.google.com/drive/folders/14dY3xK73vRKuKdXNM2naxPbPctHVnJ3L?usp=sharing'
              }
            ].map((res, idx) => (
              <RevealOnScroll key={idx} direction="up" delay={idx * 80}>
                <a
                  href={res.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group h-full bg-white border border-[#E5E5E5] rounded-2xl p-6 shadow-xs hover:shadow-lg hover:-translate-y-1 transition-all flex flex-col justify-between space-y-4"
                >
                  <div className="flex items-start justify-between">
                    <div className="p-3 rounded-xl bg-[#F6F7F3] group-hover:bg-black/5 transition-colors">
                      {res.icon}
                    </div>
                    <ArrowUpRight size={18} className="text-black/30 group-hover:text-black transition-colors" />
                  </div>

                  <div>
                    <h4 className="font-extrabold text-base text-[#000000] group-hover:text-[#1E2B1D] transition-colors">
                      {res.title}
                    </h4>
                    <p className="text-xs text-[#666666] mt-1">
                      {res.sub}
                    </p>
                  </div>
                </a>
              </RevealOnScroll>
            ))}
          </div>

          {/* PART B: Research & Academic References */}
          <RevealOnScroll direction="scale" delay={150}>
            <div className="bg-white border border-[#E5E5E5] rounded-3xl p-8 sm:p-12 shadow-sm space-y-10">
              {/* Academic Papers */}
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#F0F0F0]">
                  <h3 className="text-xl font-bold text-[#000000]">
                    Research Papers Referenced
                  </h3>
                  <a
                    href="https://drive.google.com/drive/folders/1uQrrWggW9TO94Pc_W219Vix--hPE3IwT?usp=sharing"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-bold text-emerald-800 hover:underline flex items-center gap-1.5"
                  >
                    <span>View all research paper docs (Drive)</span>
                    <ArrowUpRight size={13} />
                  </a>
                </div>

                <ol className="space-y-3.5 text-xs sm:text-sm text-[#333333]">
                  <li className="flex items-start gap-3">
                    <span className="font-bold text-[#999999] flex-shrink-0">1.</span>
                    <p className="flex-1 leading-relaxed">
                      Scalable, affordable AI-based real-time pest/disease identification using a lightweight neural network on Raspberry Pi 5.{' '}
                      <a
                        href="https://www.nature.com/articles/s41598-025-06452-5"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline inline-flex items-center gap-1 ml-1"
                      >
                        [Nature ↗]
                      </a>
                    </p>
                  </li>

                  <li className="flex items-start gap-3">
                    <span className="font-bold text-[#999999] flex-shrink-0">2.</span>
                    <p className="flex-1 leading-relaxed">
                      UAV RGB imagery + deep learning for crop disease detection and mapping — low-cost drone monitoring.{' '}
                      <a
                        href="https://www.mdpi.com/2504-446X/5/2/34"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline inline-flex items-center gap-1 ml-1"
                      >
                        [MDPI ↗]
                      </a>
                    </p>
                  </li>

                  <li className="flex items-start gap-3">
                    <span className="font-bold text-[#999999] flex-shrink-0">3.</span>
                    <p className="flex-1 leading-relaxed">
                      YOLO model benchmarking for UAV disease detection on edge devices, real-time agricultural monitoring.{' '}
                      <a
                        href="https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0349855&"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline inline-flex items-center gap-1 ml-1"
                      >
                        [PLOS ONE ↗]
                      </a>
                    </p>
                  </li>

                  <li className="flex items-start gap-3">
                    <span className="font-bold text-[#999999] flex-shrink-0">4.</span>
                    <p className="flex-1 leading-relaxed">
                      Review of autonomous drone systems — navigation, control, and operational challenges.{' '}
                      <a
                        href="https://www.sciencedirect.com/science/article/pii/S2666720724000316"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline inline-flex items-center gap-1 ml-1"
                      >
                        [ScienceDirect ↗]
                      </a>
                    </p>
                  </li>
                </ol>
              </div>

              {/* Frameworks & Tools */}
              <div className="space-y-4 pt-4 border-t border-[#F0F0F0]">
                <h3 className="text-xl font-bold text-[#000000]">
                  Tools & Frameworks Referenced
                </h3>

                <ul className="space-y-3 text-xs sm:text-sm text-[#333333]">
                  <li className="flex items-start gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1E2B1D] mt-2 flex-shrink-0" />
                    <p className="flex-1">
                      <strong>YOLO11:</strong> Official state-of-the-art object detection and instance segmentation models.{' '}
                      <a
                        href="https://docs.ultralytics.com/models/yolo11"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline ml-1"
                      >
                        [Docs ↗]
                      </a>
                    </p>
                  </li>

                  <li className="flex items-start gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1E2B1D] mt-2 flex-shrink-0" />
                    <p className="flex-1">
                      <strong>ArduPilot Mission Planner:</strong> Ground-control software for autonomous waypoint planning and monitoring.{' '}
                      <a
                        href="https://github.com/ArduPilot/MissionPlanner"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline ml-1"
                      >
                        [GitHub ↗]
                      </a>
                    </p>
                  </li>

                  <li className="flex items-start gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1E2B1D] mt-2 flex-shrink-0" />
                    <p className="flex-1">
                      <strong>MAVLink Protocol:</strong> Lightweight binary messaging protocol between companion computer and Pixhawk.{' '}
                      <a
                        href="https://mavlink.io/en/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline ml-1"
                      >
                        [Protocol ↗]
                      </a>
                    </p>
                  </li>

                  <li className="flex items-start gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1E2B1D] mt-2 flex-shrink-0" />
                    <p className="flex-1">
                      <strong>TensorFlow Lite:</strong> INT8 edge quantization runtime for rapid low-power on-device inference.{' '}
                      <a
                        href="https://www.tensorflow.org/lite/guide"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline ml-1"
                      >
                        [TFLite ↗]
                      </a>
                    </p>
                  </li>

                  <li className="flex items-start gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1E2B1D] mt-2 flex-shrink-0" />
                    <p className="flex-1">
                      <strong>PlantVillage Open Dataset:</strong> Peer-reviewed database of labeled agricultural disease imagery.{' '}
                      <a
                        href="https://arxiv.org/abs/1511.08060"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-800 font-bold hover:underline ml-1"
                      >
                        [Dataset ArXiv ↗]
                      </a>
                    </p>
                  </li>
                </ul>
              </div>
            </div>
          </RevealOnScroll>
        </div>
      </section>

      {/* 13. FUTURE SCOPE: SWARM FLEET (DARK GLASS BANNER) */}
      <section id="section-future" className="py-16 sm:py-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <RevealOnScroll direction="scale" delay={0}>
          <div className="bg-gradient-to-br from-[#182118] to-[#0D120D] text-white rounded-3xl p-8 sm:p-14 shadow-2xl border border-white/15 space-y-8">
            <div className="space-y-3 max-w-2xl">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 text-emerald-400 text-xs sm:text-sm font-bold border border-white/15">
                <Radio size={15} />
                Swarm Scale Horizon
              </div>
              <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white leading-tight">
                From One Drone to a Swarm
              </h2>
              <p className="text-sm sm:text-base text-gray-300 leading-relaxed">
                AgriVyaan is designed to scale into coordinated multi-drone swarm fleets. Multiple fields across an entire district can be surveyed concurrently with shared mission coordination and battery-aware task allocation.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 pt-4 border-t border-white/15 text-xs sm:text-sm">
              {[
                { title: '01. Multispectral NIR', desc: 'True calibrated NDVI & NDRE canopy chlorophyll mapping.' },
                { title: '02. Multi-Crop Models', desc: 'Expanded beyond potato to paddy, cotton, and sugarcane.' },
                { title: '03. Federated Learning', desc: 'Edge model updates without uploading farmer photos.' },
                { title: '04. Thermal Resilience', desc: 'Adaptive inference under high ambient field temperatures.' }
              ].map((sw, idx) => (
                <div key={idx} className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-1.5 hover:bg-white/10 transition-colors">
                  <strong className="text-emerald-400 block text-sm sm:text-base">{sw.title}</strong>
                  <p className="text-gray-300">{sw.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </RevealOnScroll>
      </section>

      {/* 14. CLOSING & ACTION CTA */}
      <section className="py-16 sm:py-24 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center space-y-8">
        <RevealOnScroll direction="scale" delay={0}>
          <div className="bg-white/85 backdrop-blur-xl border border-white/70 rounded-3xl p-8 sm:p-14 shadow-xl space-y-6">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-[#192118] leading-snug">
              “AgriVyaan doesn't replace the farmer or the agronomist — it gives them evidence, earlier, in a language they trust.”
            </h2>

            <div className="pt-3 flex justify-center">
              <button
                onClick={onBackToDashboard}
                className="px-9 py-4 bg-[#1E2B1D] hover:bg-[#2C3E2A] text-white text-base font-bold rounded-full transition-all shadow-lg hover:shadow-xl hover:scale-102 flex items-center gap-3 cursor-pointer"
              >
                <span>Launch Mission Control Dashboard</span>
                <ArrowUpRight size={18} />
              </button>
            </div>
          </div>
        </RevealOnScroll>
      </section>

      {/* Footer */}
      <footer className="border-t border-black/5 bg-white/80 py-8 px-4 text-center text-xs sm:text-sm text-[#525B50]">
        AgriVyaan · Autonomous Drone Intelligence Platform · Precision Edge Agriculture
      </footer>
      </div>
    </div>
  );
};

// Helper Icon component for folder
const FolderGit2Custom: React.FC<{ size: number; className?: string }> = ({ size, className }) => (
  <svg 
    width={size} 
    height={size} 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className={className}
  >
    <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
    <circle cx="12" cy="13" r="2" />
  </svg>
);
