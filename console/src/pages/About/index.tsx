import { Card, Typography } from "antd";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Heart, Github, Link2 } from "lucide-react";
import styles from "./index.module.less";

const { Title, Paragraph, Text } = Typography;

export default function AboutPage() {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Create floating bubbles
    const createBubbles = () => {
      const bubbles: HTMLDivElement[] = [];
      const bubbleCount = 15;

      for (let i = 0; i < bubbleCount; i++) {
        const bubble = document.createElement("div");
        bubble.className = styles.bubble;

        // Random properties
        const size = Math.random() * 60 + 20;
        const left = Math.random() * 100;
        const duration = Math.random() * 10 + 10;
        const delay = Math.random() * 5;

        bubble.style.width = `${size}px`;
        bubble.style.height = `${size}px`;
        bubble.style.left = `${left}%`;
        bubble.style.animationDuration = `${duration}s`;
        bubble.style.animationDelay = `${delay}s`;

        container.appendChild(bubble);
        bubbles.push(bubble);
      }

      return bubbles;
    };

    const bubbles = createBubbles();

    return () => {
      bubbles.forEach((bubble) => bubble.remove());
    };
  }, []);

  return (
    <div ref={containerRef} className={styles.container}>
      <div className={styles.content}>
        <Card className={styles.card} bordered={true}>
          <div className={styles.header}>
            <img src="/babyclaw.png" alt="BabyClaw" className={styles.logo} />
            <Title level={2} className={styles.title}>
              <span className={styles.textBaby}>Baby</span>
              <span className={styles.textClaw}>Claw</span>
            </Title>
          </div>

          <div className={styles.section}>
            <Title level={4}>
              <Heart className={styles.sectionIcon} size={18} />
              {t("about.mission.title")}
            </Title>
            <Paragraph className={styles.paragraph}>
              {t("about.mission.content")}
            </Paragraph>
            <Paragraph className={styles.vision}>
              {t("about.mission.vision")}
            </Paragraph>
          </div>

          <div className={styles.section}>
            <Title level={4}>
              <Github className={styles.sectionIcon} size={18} />
              {t("about.opensource.title")}
            </Title>
            <Paragraph className={styles.paragraph}>
              {t("about.opensource.content")}
            </Paragraph>
            <div className={styles.links}>
              <a
                href="https://github.com/agentscope-ai/CoPaw"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.link}
              >
                <Github size={14} />
                <span>CoPaw</span>
              </a>
              <a
                href="https://github.com/modelscope/agentscope"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.link}
              >
                <Github size={14} />
                <span>AgentScope</span>
              </a>
              <a
                href="https://github.com/anthropics/anthropic-sdk-python"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.link}
              >
                <Github size={14} />
                <span>Anthropic SDK</span>
              </a>
              <a
                href="https://github.com/openclaw/openclaw"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.link}
              >
                <Github size={14} />
                <span>OpenClaw</span>
              </a>
            </div>
          </div>

          <div className={styles.section}>
            <Title level={4}>
              <Link2 className={styles.sectionIcon} size={18} />
              {t("about.acknowledgments.title")}
            </Title>
            <Paragraph className={styles.paragraph}>
              {t("about.acknowledgments.content")}
            </Paragraph>
            <div className={styles.techStack}>
              <div className={styles.techItem}>
                <Text className={styles.techName}>FastAPI</Text>
              </div>
              <div className={styles.techItem}>
                <Text className={styles.techName}>React</Text>
              </div>
              <div className={styles.techItem}>
                <Text className={styles.techName}>TypeScript</Text>
              </div>
              <div className={styles.techItem}>
                <Text className={styles.techName}>Ant Design</Text>
              </div>
              <div className={styles.techItem}>
                <Text className={styles.techName}>Python</Text>
              </div>
              <div className={styles.techItem}>
                <Text className={styles.techName}>Uvicorn</Text>
              </div>
            </div>
          </div>

          <div className={styles.footer}>
            <Paragraph className={styles.footerText}>
              {t("about.footer")}
            </Paragraph>
          </div>
        </Card>
      </div>
    </div>
  );
}
