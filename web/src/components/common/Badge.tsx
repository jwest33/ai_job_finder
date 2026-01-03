import { HTMLAttributes, forwardRef } from 'react';
import clsx from 'clsx';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'outline';
  size?: 'sm' | 'md';
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'sm', children, ...props }, ref) => {
    const variants = {
      default: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
      success: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300',
      warning: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300',
      danger: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
      info: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
      outline: 'border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 bg-transparent',
    };

    const sizes = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-2.5 py-1 text-sm',
    };

    return (
      <span
        ref={ref}
        className={clsx(
          'inline-flex items-center font-medium rounded-full',
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {children}
      </span>
    );
  }
);

Badge.displayName = 'Badge';
