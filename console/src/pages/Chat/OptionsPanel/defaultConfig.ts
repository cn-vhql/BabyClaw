import type { TFunction } from "i18next";

const defaultConfig = {
  theme: {
    colorPrimary: "#615CED",
    darkMode: false,
    prefix: "copaw",
    leftHeader: {
      logo: "",
      title: "与 BabyClaw 共同成长",
    },
  },
  sender: {
    attachments: true,
    maxLength: 10000,
    disclaimer: "",
  },
  welcome: {
    greeting: "Hello, how can I help you today?",
    description:
      "I am a helpful assistant that can help you with your questions.",
    avatar: `${import.meta.env.BASE_URL}copaw-symbol.svg`,
    prompts: [
      {
        value: "Let's start a new journey!",
      },
      {
        value: "Can you tell me what skills you have?",
      },
    ],
  },
  api: {
    baseURL: "",
    token: "",
  },
} as const;

export function getDefaultConfig(t: TFunction) {
  return {
    ...defaultConfig,
    sender: {
      ...defaultConfig.sender,
      disclaimer: "",
    },
    welcome: {
      ...defaultConfig.welcome,
      greeting: t("chat.greeting"),
      description: t("chat.description"),
      prompts: [{ value: t("chat.prompt1") }, { value: t("chat.prompt2") }],
    },
  };
}

export default defaultConfig;

export type DefaultConfig = typeof defaultConfig;
