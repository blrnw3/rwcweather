import { Box, Heading, Table, Tbody, Td, Text, Th, Thead, Tr } from "@chakra-ui/react";
import { useContext, useEffect, useState } from "react";
import {
    annualNormal,
    CLIMATE_IS_PLACEHOLDER,
    CLIMATE_META,
    hasClimate,
    monthlyNormals,
    waterYearNormal,
} from "../../components/climate";
import { Page, UnitCtx } from "../../components/Page";
import { styleForReportValue } from "../../components/report";
import { formatObs, unitForObsType } from "../../format";

// Long-term climate normals, laid out like nw3weather's "Long-term Climate
// Averages" table: months down the side, variables across, then annual
// figures, with the current month highlighted. Everything comes from
// data/climate.js, so a revised normals file drops in without page changes:
// columns without normals there are simply not shown.

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];

// Candidate columns, in display order. `derive` columns are computed from others.
const COLUMNS = [
    { key: "tmin", group: "temp", label: "Mean low", obs: "temp", stat: "min", fmat: "temp" },
    { key: "tmax", group: "temp", label: "Mean high", obs: "temp", stat: "max", fmat: "temp" },
    { key: "tavg", group: "temp", label: "Mean", obs: "temp", stat: "avg", fmat: "temp" },
    {
        key: "trange", group: "temp", label: "Range", fmat: "abs_temp", uncoloured: true,
        derive: (get) => (get("temp", "max") != null && get("temp", "min") != null
            ? get("temp", "max") - get("temp", "min") : null),
    },
    { key: "rain", group: "rain", label: "Rainfall", obs: "rain", stat: "total", fmat: "rain", total: true },
    { key: "wind", group: "wind", label: "Mean speed", obs: "wind", stat: "avg", fmat: "wind" },
];

const GROUPS = [
    { key: "temp", label: "Temperature", fmat: "temp" },
    { key: "rain", label: "Rain", fmat: "rain" },
    { key: "wind", label: "Wind", fmat: "wind" },
];

function availableColumns() {
    return COLUMNS.filter((c) => c.derive
        ? hasClimate("temp", "min") && hasClimate("temp", "max")
        : hasClimate(c.obs, c.stat));
}

// Value of a column for a month index (0-11), or "annual" / "waterYear".
function columnValue(column, period) {
    const get = (obs, stat) => {
        if (period === "annual") {
            return annualNormal(obs, stat);
        }
        if (period === "waterYear") {
            return waterYearNormal(obs, stat);
        }
        return monthlyNormals(obs, stat)?.[period] ?? null;
    };
    if (column.derive) {
        return period === "waterYear" ? null : column.derive(get);
    }
    return get(column.obs, column.stat);
}

function ValueCell({ column, value, unit, annual }) {
    if (value == null) {
        return <Td textAlign="center" color="gray.400">&nbsp;</Td>;
    }
    const { bg, col } = column.uncoloured
        ? { bg: "transparent", col: "inherit" }
        : styleForReportValue(value, column.fmat, unit, column.total ? "total" : "avg", annual);
    return <Td className={"cell climate-" + column.key} textAlign="center" backgroundColor={bg} color={col}
        fontWeight={annual ? "bold" : "normal"} px="2" py="2">
        {formatObs(unit, value, column.fmat, false, false)}
    </Td>;
}

function ClimateTable() {
    const unit = useContext(UnitCtx);
    const columns = availableColumns();
    const groups = GROUPS.map((g) => ({ ...g, span: columns.filter((c) => c.group === g.key).length }))
        .filter((g) => g.span > 0);
    const currentMonth = new Date().getMonth();
    const hasWaterYear = columns.some((c) => columnValue(c, "waterYear") != null);
    const summaryRows = [
        { key: "annual", label: "Annual", title: "Year mean (temperature) / total (rainfall)" },
        ...(hasWaterYear ? [{ key: "waterYear", label: "Water year", title: "1 October - 30 September" }] : []),
    ];

    return <Box overflowX="auto" mt="4">
        <Table id="climate-normals-table" size="sm" variant="simple" minWidth="560px">
            <Thead>
                <Tr>
                    <Th rowSpan={2} />
                    {groups.map((g) =>
                        <Th key={g.key} colSpan={g.span} textAlign="center" borderLeft="2px solid" borderLeftColor="gray.300">
                            {g.label} / {unitForObsType(unit, g.fmat)}
                        </Th>
                    )}
                </Tr>
                <Tr>
                    {columns.map((c, i) =>
                        <Th key={c.key} textAlign="center"
                            borderLeft={i === 0 || columns[i - 1].group !== c.group ? "2px solid" : undefined}
                            borderLeftColor="gray.300">
                            {c.label}
                        </Th>
                    )}
                </Tr>
            </Thead>
            <Tbody>
                {MONTH_NAMES.map((name, m) =>
                    <Tr key={name} className={m === currentMonth ? "current-month" : undefined}
                        outline={m === currentMonth ? "2px solid" : undefined} outlineColor="orange.300">
                        <Td fontWeight="bold" title={m === currentMonth ? "Current month" : undefined}>{name}</Td>
                        {columns.map((c) => <ValueCell key={c.key} column={c} value={columnValue(c, m)} unit={unit} />)}
                    </Tr>
                )}
                {summaryRows.map((row, i) =>
                    <Tr key={row.key} borderTop={i === 0 ? "3px solid" : undefined} borderTopColor="gray.400">
                        <Td fontWeight="bold" title={row.title}>{row.label}</Td>
                        {columns.map((c) =>
                            <ValueCell key={c.key} column={c} value={columnValue(c, row.key)} unit={unit} annual />
                        )}
                    </Tr>
                )}
            </Tbody>
        </Table>
    </Box>;
}

export default function ClimateReport() {
    // The unit preference lives in localStorage, so render the (static) table
    // only on the client to avoid a server/client unit mismatch on hydration.
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);

    return <Page name="reports" sub="climate" title="Reports | climate">
        <Heading as="h1" size="1">Climate of Redwood City (Emerald Lake Hills)</Heading>
        <Heading as="h2" size="2">Long-term climate averages{CLIMATE_META.period && ", " + CLIMATE_META.period}</Heading>

        <Text mt="2">
            These are the long-term average conditions, i.e. the climate normals, at the station. The bracketed
            comparisons on the monthly, annual and daily reports are measured against them.
        </Text>
        {CLIMATE_IS_PLACEHOLDER && <Text mt="2" fontWeight="bold" color="red.600">
            These climate normals are currently placeholders, not real averages.
        </Text>}

        {mounted && <ClimateTable />}

        <Heading as="h3" size="3" mt="6">Source and methods</Heading>
        <Box id="climate-source">
            {CLIMATE_META.source && <Text mt="2"><b>Source:</b> {CLIMATE_META.source}</Text>}
            {CLIMATE_META.period && <Text mt="1"><b>Period:</b> {CLIMATE_META.period}</Text>}
            {CLIMATE_META.notes.map((note, i) => <Text key={i} mt="2">{note}</Text>)}
        </Box>
    </Page>;
}
