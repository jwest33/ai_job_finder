import { useState, useRef, DragEvent } from 'react';
import { Upload, FileText, X } from 'lucide-react';
import clsx from 'clsx';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { attachmentsApi } from '../../api/attachments';
import { AttachmentType, ATTACHMENT_TYPE_LABELS } from '../../types/job';

interface AttachmentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobUrl: string;
  onSuccess: () => void;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function AttachmentUploadModal({
  isOpen,
  onClose,
  jobUrl,
  onSuccess,
}: AttachmentUploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [attachmentType, setAttachmentType] = useState<AttachmentType>('resume');
  const [notes, setNotes] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetForm = () => {
    setSelectedFile(null);
    setAttachmentType('resume');
    setNotes('');
    setError(null);
    setIsDragOver(false);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const validateFile = (file: File): string | null => {
    // Check extension
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Invalid file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }

    // Check size
    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)}MB`;
    }

    return null;
  };

  const handleFileSelect = (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      setSelectedFile(null);
    } else {
      setError(null);
      setSelectedFile(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError(null);

    try {
      await attachmentsApi.uploadAttachment(jobUrl, selectedFile, attachmentType, notes || undefined);
      handleClose();
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Upload Attachment" size="md">
      <div className="space-y-4">
        {/* File Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={clsx(
            'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
            isDragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400',
            selectedFile && 'border-green-500 bg-green-50'
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx,.txt"
            onChange={handleFileInputChange}
            className="hidden"
          />

          {selectedFile ? (
            <div className="flex items-center justify-center gap-3">
              <FileText className="w-8 h-8 text-green-600" />
              <div className="text-left">
                <p className="font-medium text-gray-900">{selectedFile.name}</p>
                <p className="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                }}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <>
              <Upload className="w-10 h-10 mx-auto text-gray-400 mb-2" />
              <p className="text-gray-600">
                Drag and drop a file here, or click to browse
              </p>
              <p className="text-sm text-gray-400 mt-1">
                PDF, Word, or text files up to 10MB
              </p>
            </>
          )}
        </div>

        {/* Attachment Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Attachment Type
          </label>
          <div className="flex gap-4">
            {(['resume', 'cover_letter'] as AttachmentType[]).map((type) => (
              <label
                key={type}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 border rounded-lg cursor-pointer transition-colors',
                  attachmentType === type
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 hover:border-gray-400'
                )}
              >
                <input
                  type="radio"
                  name="attachmentType"
                  value={type}
                  checked={attachmentType === type}
                  onChange={() => setAttachmentType(type)}
                  className="sr-only"
                />
                {ATTACHMENT_TYPE_LABELS[type]}
              </label>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g., Tailored for remote position, emphasizes Python skills"
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={handleClose} disabled={isUploading}>
            Cancel
          </Button>
          <Button
            onClick={handleUpload}
            disabled={!selectedFile || isUploading}
            loading={isUploading}
          >
            Upload
          </Button>
        </div>
      </div>
    </Modal>
  );
}
