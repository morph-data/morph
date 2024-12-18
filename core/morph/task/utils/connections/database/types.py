from enum import Enum


class DBType(Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    REDSHIFT = "redshift"
