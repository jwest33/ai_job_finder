import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Loader2 } from 'lucide-react';
import { attachmentsApi } from '../../api/attachments';
import { AttachmentItem } from './AttachmentItem';
import { JobAttachment } from '../../types/job';

interface AttachmentListProps {
  jobUrl: string;
}

export function AttachmentList({ jobUrl }: AttachmentListProps) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['attachments', jobUrl],
    queryFn: () => attachmentsApi.getAttachments(jobUrl),
  });

  const handleDownload = async (attachment: JobAttachment) => {
    await attachmentsApi.downloadAttachment(jobUrl, attachment.id, attachment.filename);
  };

  const handleDelete = async (attachmentId: string) => {
    await attachmentsApi.deleteAttachment(jobUrl, attachmentId);
    queryClient.invalidateQueries({ queryKey: ['attachments', jobUrl] });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-500">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading attachments...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500">
        Failed to load attachments
      </div>
    );
  }

  const attachments = data?.items || [];
  const resumes = attachments.filter((a) => a.attachment_type === 'resume');
  const coverLetters = attachments.filter((a) => a.attachment_type === 'cover_letter');

  if (attachments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-gray-500">
        <FileText className="w-10 h-10 mb-2 text-gray-300" />
        <p>No attachments yet</p>
        <p className="text-sm">Upload a resume or cover letter to track it with this application</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Resumes Section */}
      {resumes.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Resumes ({resumes.length})
          </h4>
          <div className="space-y-2">
            {resumes.map((attachment) => (
              <AttachmentItem
                key={attachment.id}
                attachment={attachment}
                onDownload={() => handleDownload(attachment)}
                onDelete={() => handleDelete(attachment.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Cover Letters Section */}
      {coverLetters.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Cover Letters ({coverLetters.length})
          </h4>
          <div className="space-y-2">
            {coverLetters.map((attachment) => (
              <AttachmentItem
                key={attachment.id}
                attachment={attachment}
                onDownload={() => handleDownload(attachment)}
                onDelete={() => handleDelete(attachment.id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
