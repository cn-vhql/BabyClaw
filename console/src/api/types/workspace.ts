export interface MdFileInfo {
  filename: string;
  path: string;
  size: number;
  created_time: string;
  modified_time: string;
}

export interface MdFileContent {
  content: string;
}

export interface MarkdownFile extends MdFileInfo {
  updated_at: number;
  enabled?: boolean;
}

export interface DailyMemoryFile extends MdFileInfo {
  date: string;
  updated_at: number;
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: "file" | "folder";
  size: number;
  modified_time: string;
  children?: FileTreeNode[];
}

export interface FileContentResult {
  path: string;
  name: string;
  size: number;
  is_text: boolean;
  content: string | null;
}
