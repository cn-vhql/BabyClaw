import type { ReactNode } from "react";
import { Form } from "antd";
import type { FormListFieldData, FormListOperation } from "antd/es/form";
import { createStyles } from "antd-style";

type FormListChildren = (
  fields: FormListFieldData[],
  operation: FormListOperation,
  meta: {
    errors: ReactNode[];
    warnings: ReactNode[];
  },
) => ReactNode;

interface FormItemProps {
  name: string | string[];
  label: string;
  isList?: boolean;
  children: ReactNode | FormListChildren;
  normalize?: (value: unknown) => unknown;
}

const useStyles = createStyles(({ token }) => ({
  label: {
    marginBottom: 6,
    fontSize: 12,
    color: token.colorTextSecondary,
  },
}));

export default function FormItem(props: FormItemProps) {
  const { styles } = useStyles();

  const node = props.isList ? (
    <Form.List name={props.name}>{props.children as FormListChildren}</Form.List>
  ) : (
    <Form.Item name={props.name} normalize={props.normalize}>
      {props.children as ReactNode}
    </Form.Item>
  );

  return (
    <div>
      {props.label && <div className={styles.label}>{props.label}</div>}
      {node}
    </div>
  );
}
