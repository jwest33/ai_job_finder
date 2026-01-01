import { useState } from 'react';
import { FileText, FileType, Download, Trash2, Loader2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import { JobAttachment, ATTACHMENT_TYPE_LABELS, ATTACHMENT_TYPE_COLORS } from '../../types/job';
import { Badge } from '../common/Badge';

interface AttachmentItemProps {
  attachment: JobAttachment;
  onDownload: () => Promise<void>;
  onDelete: () => Promise<void>;
}

export function AttachmentItem({ attachment, onDownload, onDelete }: AttachmentItemProps) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      await onDownload();
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete();
    } finally {
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const getFileIcon = () => {
    const iconClass = 'w-8 h-8';
    switch (attachment.file_extension) {
      case '.pdf':
        return <FileText className={clsx(iconClass, 'text-red-500')} />;
      case '.doc':
      case '.docx':
        return <FileType className={clsx(iconClass, 'text-blue-500')} />;
      default:
        return <FileText className={clsx(iconClass, 'text-gray-500')} />;
    }
  };

  const truncateFilename = (filename: string, maxLength: number = 35) => {
    if (filename.length <= maxLength) return filename;
    const ext = filename.lastIndexOf('.');
    if (ext === -1) return filename.slice(0, maxLength - 3) + '...';
    const name = filename.slice(0, ext);
    const extension = filename.slice(ext);
    const truncatedName = name.slice(0, maxLength - extension.length - 3) + '...';
    return truncatedName + extension;
  };

  return (
    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
      {/* File Icon */}
      <div className="flex-shrink-0">{getFileIcon()}</div>

      {/* File Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className="font-medium text-gray-900 truncate"
            title={attachment.filename}
          >
            {truncateFilename(attachment.filename)}
          </span>
          <Badge className={ATTACHMENT_TYPE_COLORS[attachment.attachment_type]} size="sm">
            {ATTACHMENT_TYPE_LABELS[attachment.attachment_type]}
          </Badge>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500 mt-0.5">
          <span>{attachment.file_size_display}</span>
          <span>-</span>
          <span>
            {formatDistanceToNow(new Date(attachment.created_at), { addSuffix: true })}
          </span>
        </div>
        {attachment.notes && (
          <p className="text-sm text-gray-600 mt-1 line-clamp-1">{attachment.notes}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        {showDeleteConfirm ? (
          <>
            <button
              onClick={() => setShowDeleteConfirm(false)}
              className="px-2 py-1 text-xs text-gray-600 hover:text-gray-800"
              disabled={isDeleting}
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
              disabled={isDeleting}
            >
              {isDeleting ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                'Confirm'
              )}
            </button>
          </>
        ) : (
          <>
            <button
              onClick={handleDownload}
              className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
              title="Download"
              disabled={isDownloading}
            >
              {isDownloading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
              title="Delete"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
