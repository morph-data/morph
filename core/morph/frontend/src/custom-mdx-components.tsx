import {
  Accordion,
  Alert,
  Card,
  DataTable,
  Embed,
  Grid,
  Img,
  LLM,
  Metrics,
  MetricsGrid,
  Panel,
  Stack,
  Tab,
  Tabs,
  VarDatePicker,
  VariableDatePicker,
  VariableInput,
  VariableSelect,
  VariableValue,
  VarInput,
  VarValue,
} from "@use-morph/page";
import { MDXComponents } from "mdx/types";

export const customMDXComponents: MDXComponents = {
  DataTable(properties) {
    return <DataTable {...properties} />;
  },
  Embed(properties) {
    return <Embed {...properties} />;
  },
  Metrics(properties) {
    return <Metrics {...properties} />;
  },
  MetricsGrid(properties) {
    return <MetricsGrid {...properties} />;
  },
  VariableInput(properties) {
    return <VariableInput {...properties} />;
  },
  VarInput(properties) {
    return <VarInput {...properties} />;
  },
  VariableValue(properties) {
    return <VariableValue {...properties} />;
  },
  VarValue(properties) {
    return <VarValue {...properties} />;
  },
  VariableDatePicker(properties) {
    return <VariableDatePicker {...properties} />;
  },
  VarDatePicker(properties) {
    return <VarDatePicker {...properties} />;
  },
  VariableSelect: function (properties) {
    return <VariableSelect.Root {...properties} />;
  },
  VarSelect: function (properties) {
    return <VariableSelect.Root {...properties} />;
  },
  VariableSelectGroup: function (properties) {
    return <VariableSelect.Group {...properties} />;
  },
  VarSelectGroup: function (properties) {
    return <VariableSelect.Group {...properties} />;
  },
  VariableSelectLabel: function (properties) {
    return <VariableSelect.Label {...properties} />;
  },
  VarSelectLabel: function (properties) {
    return <VariableSelect.Label {...properties} />;
  },
  VariableSelectItem: function (properties) {
    return <VariableSelect.Item {...properties} />;
  },
  VarSelectItem: function (properties) {
    return <VariableSelect.Item {...properties} />;
  },
  VariableSelectItems: function (properties) {
    return <VariableSelect.Items {...properties} />;
  },
  VarSelectItems: function (properties) {
    return <VariableSelect.Items {...properties} />;
  },
  VariableSelectSeparator: function (properties) {
    return <VariableSelect.Separator {...properties} />;
  },
  VarSelectSeparator: function (properties) {
    return <VariableSelect.Separator {...properties} />;
  },
  Value: function (properties) {
    return <VariableValue {...properties} />;
  },
  Stack(properties) {
    return <Stack {...properties} />;
  },
  Card(properties) {
    return <Card.Root {...properties} />;
  },
  Grid(properties) {
    return <Grid {...properties} />;
  },
  Panel(properties) {
    return <Panel {...properties} />;
  },
  Tabs(properties) {
    return <Tabs {...properties} />;
  },
  Tab(properties) {
    return <Tab {...properties} />;
  },
  Accordion(properties) {
    return <Accordion {...properties} />;
  },
  Alert(properties) {
    return <Alert {...properties} />;
  },
  Img(properties) {
    return <Img {...properties} />;
  },
  LLM(properties) {
    return <LLM {...properties} />;
  },
};
