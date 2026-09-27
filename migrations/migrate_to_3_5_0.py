"""
Portal 3.5.0: Produktinstanzen für individuelle Inventarverwaltung.

Fügt neue Tabellen hinzu:
- product_instances: Individuelle physische Exemplare von Produkten
- inventory_colors: Benutzerdefinierte Farben für Inventar
- product_instance_status_history: Statushistorie für Instanzen

Erweitert bestehende Tabellen:
- borrow_transactions: instance_id Feld
- checkout_items: instance_id Feld
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run(db=None, report=None):
    from sqlalchemy import inspect, text, Table, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
    from sqlalchemy.dialects import mysql, sqlite
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    if db is None:
        from app import create_app, db as _db
        app = create_app()
        ctx = app.app_context()
        ctx.push()
        db = _db
    else:
        ctx = None

    class _Nop:
        def note_ok(self, *a, **k): pass
        def note_warn(self, *a, **k): pass
        def note_skip(self, *a, **k): pass
        def note_error(self, *a, **k): pass

    report = report or _Nop()

    try:
        inspector = inspect(db.engine)
        dialect = db.engine.dialect.name
        
        # 1. Neue Tabelle: product_instances
        table_name = 'product_instances'
        if table_name not in inspector.get_table_names():
            with db.engine.begin() as conn:
                if dialect == 'sqlite':
                    from alembic.migration import MigrationContext
                    from alembic.operations import Operations
                    
                    ctx_mig = MigrationContext.configure(conn)
                    op = Operations(ctx_mig)
                    
                    op.create_table(
                        table_name,
                        Column('id', Integer, primary_key=True),
                        Column('product_id', Integer, ForeignKey('products.id'), nullable=False, index=True),
                        Column('inventory_number', String(100), nullable=True, index=True),
                        Column('serial_number', String(100), nullable=True, index=True),
                        Column('status', String(20), default='available', nullable=False, index=True),
                        Column('dguv_enabled', Boolean, default=False, nullable=False, index=True),
                        Column('dguv_id', String(100), nullable=True, index=True),
                        Column('color_id', Integer, ForeignKey('inventory_colors.id'), nullable=True, index=True),
                        Column('color_override', String(7), nullable=True),
                        Column('location', String(255), nullable=True, index=True),
                        Column('assigned_user_id', Integer, ForeignKey('users.id'), nullable=True, index=True),
                        Column('notes', Text, nullable=True),
                        Column('active', Boolean, default=True, nullable=False, index=True),
                        Column('created_by', Integer, ForeignKey('users.id'), nullable=False),
                        Column('created_at', DateTime, default='CURRENT_TIMESTAMP', nullable=False),
                        Column('updated_at', DateTime, default='CURRENT_TIMESTAMP', onupdate='CURRENT_TIMESTAMP', nullable=False),
                    )
                    report.note_ok(f'{table_name} erstellt')
                else:
                    conn.execute(text(f"""
                        CREATE TABLE {table_name} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            product_id INTEGER NOT NULL,
                            inventory_number VARCHAR(100),
                            serial_number VARCHAR(100),
                            status VARCHAR(20) DEFAULT 'available' NOT NULL,
                            dguv_enabled BOOLEAN DEFAULT FALSE NOT NULL,
                            dguv_id VARCHAR(100),
                            color_id INTEGER,
                            color_override VARCHAR(7),
                            location VARCHAR(255),
                            assigned_user_id INTEGER,
                            notes TEXT,
                            active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_by INTEGER NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
                            FOREIGN KEY (product_id) REFERENCES products(id),
                            FOREIGN KEY (color_id) REFERENCES inventory_colors(id),
                            FOREIGN KEY (assigned_user_id) REFERENCES users(id),
                            FOREIGN KEY (created_by) REFERENCES users(id)
                        )
                    """))
                    report.note_ok(f'{table_name} erstellt ({dialect})')
        else:
            report.note_skip(f'{table_name} existiert bereits')
        
        # 2. Neue Tabelle: inventory_colors
        table_name = 'inventory_colors'
        if table_name not in inspector.get_table_names():
            with db.engine.begin() as conn:
                if dialect == 'sqlite':
                    ctx_mig = MigrationContext.configure(conn)
                    op = Operations(ctx_mig)
                    
                    op.create_table(
                        table_name,
                        Column('id', Integer, primary_key=True),
                        Column('name', String(100), nullable=False, unique=True, index=True),
                        Column('color_hex', String(7), nullable=False),
                        Column('description', String(255), nullable=True),
                        Column('sort_order', Integer, default=0, nullable=False),
                        Column('active', Boolean, default=True, nullable=False, index=True),
                        Column('created_by', Integer, ForeignKey('users.id'), nullable=False),
                        Column('created_at', DateTime, default='CURRENT_TIMESTAMP', nullable=False),
                        Column('updated_at', DateTime, default='CURRENT_TIMESTAMP', onupdate='CURRENT_TIMESTAMP', nullable=False),
                    )
                    report.note_ok(f'{table_name} erstellt')
                else:
                    conn.execute(text(f"""
                        CREATE TABLE {table_name} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(100) NOT NULL UNIQUE,
                            color_hex VARCHAR(7) NOT NULL,
                            description VARCHAR(255),
                            sort_order INTEGER DEFAULT 0 NOT NULL,
                            active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_by INTEGER NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
                            FOREIGN KEY (created_by) REFERENCES users(id)
                        )
                    """))
                    report.note_ok(f'{table_name} erstellt ({dialect})')
        else:
            report.note_skip(f'{table_name} existiert bereits')
        
        # 3. Neue Tabelle: product_instance_status_history
        table_name = 'product_instance_status_history'
        if table_name not in inspector.get_table_names():
            with db.engine.begin() as conn:
                if dialect == 'sqlite':
                    ctx_mig = MigrationContext.configure(conn)
                    op = Operations(ctx_mig)
                    
                    op.create_table(
                        table_name,
                        Column('id', Integer, primary_key=True),
                        Column('instance_id', Integer, ForeignKey('product_instances.id'), nullable=False, index=True),
                        Column('old_status', String(20), nullable=True, index=True),
                        Column('new_status', String(20), nullable=False, index=True),
                        Column('reason', String(255), nullable=True),
                        Column('note', Text, nullable=True),
                        Column('changed_by', Integer, ForeignKey('users.id'), nullable=False),
                        Column('changed_at', DateTime, default='CURRENT_TIMESTAMP', nullable=False, index=True),
                    )
                    report.note_ok(f'{table_name} erstellt')
                else:
                    conn.execute(text(f"""
                        CREATE TABLE {table_name} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            instance_id INTEGER NOT NULL,
                            old_status VARCHAR(20),
                            new_status VARCHAR(20) NOT NULL,
                            reason VARCHAR(255),
                            note TEXT,
                            changed_by INTEGER NOT NULL,
                            changed_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            FOREIGN KEY (instance_id) REFERENCES product_instances(id),
                            FOREIGN KEY (changed_by) REFERENCES users(id)
                        )
                    """))
                    report.note_ok(f'{table_name} erstellt ({dialect})')
        else:
            report.note_skip(f'{table_name} existiert bereits')
        
        # 4. borrow_transactions erweitern: instance_id
        table_name = 'borrow_transactions'
        if table_name in inspector.get_table_names():
            cols = {c['name']: c for c in inspector.get_columns(table_name)}
            if 'instance_id' not in cols:
                with db.engine.begin() as conn:
                    if dialect == 'sqlite':
                        ctx_mig = MigrationContext.configure(conn)
                        op = Operations(ctx_mig)
                        with op.batch_alter_table(table_name) as batch_op:
                            batch_op.add_column(Column('instance_id', Integer, ForeignKey('product_instances.id'), nullable=True, index=True))
                        report.note_ok(f'{table_name}.instance_id hinzugefügt (sqlite batch)')
                    elif dialect == 'mysql':
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD COLUMN instance_id INT NULL, ADD INDEX idx_{table_name}_instance_id (instance_id)'
                        ))
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD CONSTRAINT fk_{table_name}_instance_id FOREIGN KEY (instance_id) REFERENCES product_instances(id)'
                        ))
                        report.note_ok(f'{table_name}.instance_id hinzugefügt (mysql)')
                    else:
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD COLUMN instance_id INT NULL'
                        ))
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD FOREIGN KEY (instance_id) REFERENCES product_instances(id)'
                        ))
                        report.note_ok(f'{table_name}.instance_id hinzugefügt ({dialect})')
            else:
                report.note_skip(f'{table_name}.instance_id existiert bereits')
        
        # 5. checkout_items erweitern: instance_id
        table_name = 'checkout_items'
        if table_name in inspector.get_table_names():
            cols = {c['name']: c for c in inspector.get_columns(table_name)}
            if 'instance_id' not in cols:
                with db.engine.begin() as conn:
                    if dialect == 'sqlite':
                        ctx_mig = MigrationContext.configure(conn)
                        op = Operations(ctx_mig)
                        with op.batch_alter_table(table_name) as batch_op:
                            batch_op.add_column(Column('instance_id', Integer, ForeignKey('product_instances.id'), nullable=True, index=True))
                        report.note_ok(f'{table_name}.instance_id hinzugefügt (sqlite batch)')
                    elif dialect == 'mysql':
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD COLUMN instance_id INT NULL, ADD INDEX idx_{table_name}_instance_id (instance_id)'
                        ))
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD CONSTRAINT fk_{table_name}_instance_id FOREIGN KEY (instance_id) REFERENCES product_instances(id)'
                        ))
                        report.note_ok(f'{table_name}.instance_id hinzugefügt (mysql)')
                    else:
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD COLUMN instance_id INT NULL'
                        ))
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD FOREIGN KEY (instance_id) REFERENCES product_instances(id)'
                        ))
                        report.note_ok(f'{table_name}.instance_id hinzugefügt ({dialect})')
            else:
                report.note_skip(f'{table_name}.instance_id existiert bereits')
        
        report.note_ok('migrate_to_3_5_0 abgeschlossen')
    except Exception as exc:
        report.note_error(f'migrate_to_3_5_0 fehlgeschlagen: {exc}')
        raise
    finally:
        if ctx is not None:
            ctx.pop()


if __name__ == '__main__':
    run()
