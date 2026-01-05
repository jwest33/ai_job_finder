import { useState, useRef, useCallback, useEffect } from 'react';
import { GripHorizontal } from 'lucide-react';
import clsx from 'clsx';

interface ResizableContainerProps {
  children: React.ReactNode;
  minHeight?: number;
  maxHeight?: number;
  defaultHeight?: number;
  storageKey?: string;
  className?: string;
}

export function ResizableContainer({
  children,
  minHeight = 300,
  maxHeight = 1200,
  defaultHeight = 600,
  storageKey,
  className
}: ResizableContainerProps) {
  // Load saved height from localStorage if storageKey provided
  const getInitialHeight = () => {
    if (storageKey) {
      const saved = localStorage.getItem(`resize-height-${storageKey}`);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= minHeight && parsed <= maxHeight) {
          return parsed;
        }
      }
    }
    return defaultHeight;
  };

  const [height, setHeight] = useState(getInitialHeight);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const startYRef = useRef(0);
  const startHeightRef = useRef(0);

  // Save height to localStorage when it changes
  useEffect(() => {
    if (storageKey) {
      localStorage.setItem(`resize-height-${storageKey}`, height.toString());
    }
  }, [height, storageKey]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startYRef.current = e.clientY;
    startHeightRef.current = height;
  }, [height]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return;

    const deltaY = e.clientY - startYRef.current;
    const newHeight = Math.min(maxHeight, Math.max(minHeight, startHeightRef.current + deltaY));
    setHeight(newHeight);
  }, [isDragging, minHeight, maxHeight]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Add/remove global mouse event listeners
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return (
    <div
      ref={containerRef}
      className={clsx('relative flex flex-col', className)}
      style={{ height: `${height}px` }}
    >
      {/* Content area */}
      <div className="flex-1 overflow-hidden">
        {children}
      </div>

      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDown}
        className={clsx(
          'absolute bottom-0 left-0 right-0 h-3 cursor-ns-resize flex items-center justify-center',
          'bg-gray-100 dark:bg-gray-700 border-t border-gray-200 dark:border-gray-600',
          'hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
          isDragging && 'bg-blue-100 dark:bg-blue-900'
        )}
      >
        <GripHorizontal className="w-4 h-4 text-gray-400 dark:text-gray-500" />
      </div>
    </div>
  );
}
