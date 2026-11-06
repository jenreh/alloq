"""Preserve target routine/type ACLs and schema-scoped default privileges."""

from collections import defaultdict
from typing import LiteralString

from psycopg import AsyncConnection, sql


def _recipient(name: str | None) -> sql.Composable:
    return sql.SQL("PUBLIC") if name is None else sql.Identifier(name)


def _do(body: str) -> str:
    return sql.SQL("DO {};\n").format(sql.Literal(body)).as_string()


def reset_acl(
    catalog: str,
    column: str,
    oid: sql.Composable,
    kind: sql.Composable,
    target: sql.Composable,
) -> sql.Composable:
    """Remove restored defaults too, including grants to named roles."""
    revoke = sql.SQL("REVOKE ALL ON {} {} FROM ").format(kind, target).as_string()
    body = (
        sql.SQL(
            "DECLARE acl_role text; BEGIN FOR acl_role IN "
            "SELECT pg_get_userbyid(a.grantee) FROM {} o "
            "CROSS JOIN LATERAL aclexplode(o.{}) a "
            "WHERE o.oid={} AND a.grantee<>0 LOOP "
            "EXECUTE {} || quote_ident(acl_role); END LOOP; "
        )
        .format(
            sql.Identifier(catalog), sql.Identifier(column), oid, sql.Literal(revoke)
        )
        .as_string()
    )
    body += revoke + "PUBLIC; END"
    return sql.SQL("DO {};\n").format(sql.Literal(body))


async def additional_grants(connection: AsyncConnection) -> str:
    statements = ["SET LOCAL search_path=pg_catalog,public;"]
    routines: dict[tuple, list] = defaultdict(list)
    cursor = await connection.execute(
        "SELECT n.nspname,p.proname,oidvectortypes(p.proargtypes),p.prokind, "
        "pg_get_userbyid(p.proowner),a.grantee,pg_get_userbyid(a.grantee), "
        "a.privilege_type,a.is_grantable "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "LEFT JOIN LATERAL "
        "aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a ON true "
        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'"
    )
    for (
        schema,
        name,
        args,
        kind,
        owner,
        oid,
        recipient,
        privilege,
        grantable,
    ) in await cursor.fetchall():
        key = (schema, name, args, kind, owner)
        if oid is not None:
            routines[key].append(
                (None if oid == 0 else recipient, privilege, grantable)
            )
        else:
            routines[key]
    for (schema, name, args, kind, owner), grants in routines.items():
        target = sql.SQL("{}.{}({})").format(
            sql.Identifier(schema), sql.Identifier(name), sql.SQL(args)
        )
        noun = sql.SQL("PROCEDURE" if kind == "p" else "FUNCTION")
        reset = reset_acl(
            "pg_proc",
            "proacl",
            sql.SQL("to_regprocedure({})").format(sql.Literal(target.as_string())),
            noun,
            target,
        )
        statements.append(
            _do(
                sql.SQL("BEGIN IF to_regprocedure({}) IS NOT NULL THEN {} END IF; END")
                .format(sql.Literal(target.as_string()), reset)
                .as_string()
            )
        )
        body = (
            sql.SQL(
                "BEGIN IF to_regprocedure({}) IS NOT NULL THEN "
                "ALTER ROUTINE {} OWNER TO {}; REVOKE ALL ON {} {} FROM PUBLIC; "
            )
            .format(
                sql.Literal(target.as_string()),
                target,
                sql.Identifier(owner),
                noun,
                target,
            )
            .as_string()
        )
        for recipient, privilege, grantable in grants:
            body += (
                sql.SQL("GRANT {} ON {} {} TO {}{}; ")
                .format(
                    sql.SQL(privilege),
                    noun,
                    target,
                    _recipient(recipient),
                    sql.SQL(" WITH GRANT OPTION" if grantable else ""),
                )
                .as_string()
            )
        statements.append(_do(body + "END IF; END"))

    defaults: dict[tuple, list] = defaultdict(list)
    cursor = await connection.execute(
        "SELECT n.nspname,pg_get_userbyid(d.defaclrole),d.defaclobjtype, "
        "a.grantee,pg_get_userbyid(a.grantee),a.privilege_type,a.is_grantable "
        "FROM pg_default_acl d JOIN pg_namespace n ON n.oid=d.defaclnamespace "
        "LEFT JOIN LATERAL aclexplode(d.defaclacl) a ON true "
        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'"
    )
    for (
        schema,
        owner,
        kind,
        oid,
        recipient,
        privilege,
        grantable,
    ) in await cursor.fetchall():
        defaults[(schema, owner, kind)].append(
            (None if oid == 0 else recipient, privilege, grantable)
        )
    kinds: dict[str, LiteralString] = {
        "r": "TABLES",
        "S": "SEQUENCES",
        "f": "FUNCTIONS",
        "T": "TYPES",
    }
    for (schema, owner, kind), grants in defaults.items():
        if kind not in kinds:
            continue
        prefix = (
            sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} ")
            .format(sql.Identifier(owner), sql.Identifier(schema))
            .as_string()
        )
        body = (
            sql.SQL(
                "BEGIN IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname={}) THEN "
            )
            .format(sql.Literal(schema))
            .as_string()
        )
        body += prefix + "REVOKE ALL ON " + kinds[kind] + " FROM PUBLIC; "
        for recipient, privilege, grantable in grants:
            if privilege is not None:
                body += (
                    prefix
                    + sql.SQL("GRANT {} ON {} TO {}{}; ")
                    .format(
                        sql.SQL(privilege),
                        sql.SQL(kinds[kind]),
                        _recipient(recipient),
                        sql.SQL(" WITH GRANT OPTION" if grantable else ""),
                    )
                    .as_string()
                )
        statements.append(_do(body + "END IF; END"))
    statements.append(await type_grants(connection))
    return "\n".join(statements)


async def type_grants(connection: AsyncConnection) -> str:
    types: dict[tuple, list] = defaultdict(list)
    cursor = await connection.execute(
        "SELECT n.nspname,t.typname,pg_get_userbyid(t.typowner), "
        "a.grantee,pg_get_userbyid(a.grantee),a.privilege_type,a.is_grantable "
        "FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
        "LEFT JOIN LATERAL aclexplode(t.typacl) a ON true "
        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
        "AND t.typacl IS NOT NULL"
    )
    for (
        schema,
        name,
        owner,
        oid,
        recipient,
        privilege,
        grantable,
    ) in await cursor.fetchall():
        key = (schema, name, owner)
        if oid is not None:
            types[key].append((None if oid == 0 else recipient, privilege, grantable))
        else:
            types[key]
    statements = []
    for (schema, name, owner), grants in types.items():
        target = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))
        reset = reset_acl(
            "pg_type",
            "typacl",
            sql.SQL("to_regtype({})").format(sql.Literal(target.as_string())),
            sql.SQL("TYPE"),
            target,
        )
        body = (
            sql.SQL(
                "BEGIN IF to_regtype({}) IS NOT NULL THEN "
                "ALTER TYPE {} OWNER TO {}; {} "
            )
            .format(
                sql.Literal(target.as_string()), target, sql.Identifier(owner), reset
            )
            .as_string()
        )
        for recipient, privilege, grantable in grants:
            body += (
                sql.SQL("GRANT {} ON TYPE {} TO {}{}; ")
                .format(
                    sql.SQL(privilege),
                    target,
                    _recipient(recipient),
                    sql.SQL(" WITH GRANT OPTION" if grantable else ""),
                )
                .as_string()
            )
        statements.append(_do(body + "END IF; END"))
    return "\n".join(statements)
