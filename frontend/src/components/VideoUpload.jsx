import { useRef, useState } from "react";
import { UploadCloud, Film, X } from "lucide-react";

export default function VideoUpload({ file, setFile }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  function acceptFile(candidate) {
    if (!candidate) return;
    if (!candidate.type.startsWith("video/")) {
      alert("Please select a video file.");
      return;
    }
    setFile(candidate);
  }

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault(); setDragging(false);
        acceptFile(e.dataTransfer.files?.[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm"
        hidden
        onChange={(e) => acceptFile(e.target.files?.[0])}
      />
      {file ? (
        <div className="selected-file">
          <Film size={28} />
          <div className="file-details">
            <strong>{file.name}</strong>
            <span>{(file.size / (1024 * 1024)).toFixed(1)} MB</span>
          </div>
          <button className="icon-button" type="button" onClick={() => setFile(null)} aria-label="Remove file">
            <X size={18} />
          </button>
        </div>
      ) : (
        <>
          <div className="upload-icon"><UploadCloud size={30} /></div>
          <strong>Drop your video here</strong>
          <span>or select a file from your computer</span>
          <button type="button" className="button secondary" onClick={() => inputRef.current?.click()}>
            Choose video
          </button>
          <small>MP4, MOV, AVI, MKV or WebM · Max 100 MB</small>
        </>
      )}
    </div>
  );
}
