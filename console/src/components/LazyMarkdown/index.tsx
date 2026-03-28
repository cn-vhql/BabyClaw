import { lazy, Suspense, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import styles from "./index.module.less";

const MarkdownRenderer = lazy(() =>
  import("@ant-design/x-markdown").then((module) => ({
    default: module.XMarkdown,
  })),
);

interface LazyMarkdownProps {
  content: string;
  className?: string;
  style?: CSSProperties;
  fallbackClassName?: string;
}

export function LazyMarkdown({
  content,
  className,
  style,
  fallbackClassName,
}: LazyMarkdownProps) {
  const { t } = useTranslation();
  const fallbackClasses = [styles.loading, fallbackClassName]
    .filter(Boolean)
    .join(" ");

  return (
    <Suspense fallback={<div className={fallbackClasses}>{t("common.loading")}</div>}>
      <MarkdownRenderer content={content} className={className} style={style} />
    </Suspense>
  );
}
