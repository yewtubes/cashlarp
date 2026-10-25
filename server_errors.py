class AuthError(Exception):
    def __init__(self,status,message):self.status,self.message=status,message
