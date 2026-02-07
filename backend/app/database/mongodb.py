"""
MongoDB Client - Persistent storage for masked conversations
"""
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, List, Optional
from datetime import datetime
import logging
import uuid

from ..core.config import settings

logger = logging.getLogger(__name__)


class MongoDBClient:
    """
    MongoDB client for storing masked conversation history
    
    Features:
    - Async operations with Motor
    - Session management
    - Message storage with masked content only
    - User statistics
    """
    
    def __init__(self, uri: str = None, db_name: str = None):
        """
        Initialize MongoDB connection
        
        Args:
            uri: MongoDB connection URI
            db_name: Database name
        """
        self.uri = uri or settings.MONGODB_URI
        self.db_name = db_name or settings.MONGODB_DB_NAME
        
        if not self.uri:
            logger.warning("MongoDB URI not configured")
            self.client = None
            self.db = None
            self.encrypted_profiles = None
            return

        # Initialize client
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]

        # Collections
        self.sessions = self.db.sessions
        self.messages = self.db.messages
        self.users = self.db.users
        self.stats = self.db.stats
        self.encrypted_profiles = self.db.encrypted_profiles
        
        logger.info(f"MongoDB client initialized for database: {self.db_name}")
    
    async def create_indexes(self):
        """Create database indexes"""
        try:
            await self.sessions.create_index("user_id")
            await self.sessions.create_index("created_at")
            await self.messages.create_index("session_id")
            await self.messages.create_index([("session_id", 1), ("timestamp", 1)])
            if self.encrypted_profiles is not None:
                await self.encrypted_profiles.create_index("updated_at")
            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    # Session operations
    
    async def create_session(self, user_id: str = "anonymous", title: str = None) -> str:
        """
        Create a new chat session
        
        Args:
            user_id: User identifier
            title: Optional session title
            
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        
        session = {
            "_id": session_id,
            "user_id": user_id,
            "title": title or "New Chat",
            "created_at": datetime.utcnow(),
            "last_active": datetime.utcnow(),
            "message_count": 0,
            "token_count": 0,
        }
        
        await self.sessions.insert_one(session)
        logger.debug(f"Created session: {session_id}")
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        session = await self.sessions.find_one({"_id": session_id})
        return session
    
    async def update_session(self, session_id: str, updates: Dict):
        """Update session metadata"""
        updates["last_active"] = datetime.utcnow()
        await self.sessions.update_one(
            {"_id": session_id},
            {"$set": updates}
        )
    
    async def delete_session(self, session_id: str):
        """Delete a session and its messages"""
        await self.messages.delete_many({"session_id": session_id})
        await self.sessions.delete_one({"_id": session_id})
        logger.info(f"Deleted session: {session_id}")
    
    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict]:
        """Get all sessions for a user"""
        cursor = self.sessions.find(
            {"user_id": user_id}
        ).sort("last_active", -1).skip(skip).limit(limit)
        
        sessions = await cursor.to_list(length=limit)
        return sessions
    
    # Message operations
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        masked_content: str,
        tokens_used: List[str] = None
    ) -> str:
        """
        Add a message to a session (MASKED ONLY)
        
        Args:
            session_id: Session ID
            role: "user" or "assistant"
            masked_content: The masked version of the message
            tokens_used: List of tokens used in this message
            
        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        
        message = {
            "_id": message_id,
            "session_id": session_id,
            "role": role,
            "masked_content": masked_content,  # Only store masked!
            "tokens_used": tokens_used or [],
            "timestamp": datetime.utcnow(),
        }
        
        await self.messages.insert_one(message)
        
        # Update session
        await self.sessions.update_one(
            {"_id": session_id},
            {
                "$set": {"last_active": datetime.utcnow()},
                "$inc": {"message_count": 1}
            }
        )
        
        return message_id
    
    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get all messages for a session"""
        cursor = self.messages.find(
            {"session_id": session_id}
        ).sort("timestamp", 1).limit(limit)
        
        messages = await cursor.to_list(length=limit)
        return messages
    
    async def get_message(self, message_id: str) -> Optional[Dict]:
        """Get a specific message"""
        return await self.messages.find_one({"_id": message_id})
    
    # Statistics
    
    async def get_user_stats(self, user_id: str) -> Dict:
        """Get privacy statistics for a user"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_sessions": {"$sum": 1},
                "total_messages": {"$sum": "$message_count"},
                "total_tokens": {"$sum": "$token_count"},
            }}
        ]
        
        cursor = self.sessions.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        if result:
            return result[0]
        return {
            "total_sessions": 0,
            "total_messages": 0,
            "total_tokens": 0,
        }
    
    async def increment_stats(
        self,
        user_id: str,
        pii_detected: int = 0,
        tokens_generated: int = 0
    ):
        """Increment user statistics"""
        await self.stats.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "pii_detected": pii_detected,
                    "tokens_generated": tokens_generated,
                },
                "$set": {"last_updated": datetime.utcnow()}
            },
            upsert=True
        )
    
    # Health check
    
    async def health_check(self) -> Dict:
        """Check MongoDB connection health"""
        if not self.client:
            return {"status": "not_configured", "connected": False}
        
        try:
            await self.client.admin.command('ping')
            return {
                "status": "healthy",
                "connected": True,
                "database": self.db_name
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }


# Singleton
_mongodb = None

async def get_mongodb() -> MongoDBClient:
    global _mongodb
    if _mongodb is None:
        _mongodb = MongoDBClient()
        await _mongodb.create_indexes()
    return _mongodb
